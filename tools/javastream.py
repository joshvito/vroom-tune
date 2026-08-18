"""Minimal Java ObjectInputStream stream walker for REW .mdat files.
Extracts, in stream order:
  ('classdesc', name, flags, nfields)
  ('object', classname)
  ('arrdata', '[D'|'[F', length, data)
  ('objarray', classname, length)
  ('string', value)
  ('enum', classname, const)
"""
import struct, sys, io

MAGIC=b"\xac\xed"; VERSION=b"\x00\x05"
TC_NULL=0x70; TC_REFERENCE=0x71; TC_CLASSDESC=0x72; TC_OBJECT=0x73
TC_STRING=0x74; TC_ARRAY=0x75; TC_CLASS=0x76; TC_BLOCKDATA=0x77
TC_ENDBLOCKDATA=0x78; TC_RESET=0x79; TC_BLOCKDATALONG=0x7A
TC_EXCEPTION=0x7B; TC_LONGSTRING=0x7C; TC_PROXYCLASSDESC=0x7D; TC_ENUM=0x7E
SC_WRITE_METHOD=0x01; SC_SERIALIZABLE=0x02; SC_EXTERNALIZABLE=0x04
SC_BLOCKDATA=0x08; SC_ENUM=0x10
BASE_HANDLE=0x7E0000
ITYPE_MAP={'B':1,'Z':1,'C':2,'S':2,'I':4,'J':8,'F':4,'D':8}

class ClassDesc:
    __slots__=("name","flags","fields","super_","handle")
    def __init__(s): s.name=""; s.flags=0; s.fields=[]; s.super_=None; s.handle=0
    def chain(s):
        out=[]; d=s
        while d: out.append(d); d=d.super_
        return list(reversed(out))

class Reader:
    def __init__(s,data):
        s.d=data; s.pos=0; s.handle=BASE_HANDLE
        s.objs={}; s.events=[]; s.cur=None
        s.fpath=[]  # (classname, fieldname) stack during object reads
        s.peek=set()
    def bytes(s,n):
        if n<0 or s.pos+n>len(s.d): raise EOFError("need %d bytes at %d of %d"%(n,s.pos,len(s.d)))
        b=s.d[s.pos:s.pos+n]; s.pos+=n; return b
    def u1(s): return s.bytes(1)[0]
    def u2(s): return struct.unpack(">H",s.bytes(2))[0]
    def i4(s): return struct.unpack(">i",s.bytes(4))[0]
    def u4(s): return struct.unpack(">I",s.bytes(4))[0]
    def mod_utf(s):
        n=s.u2(); b=s.bytes(n)
        return b.decode("utf-8","replace")
    def read_prim(s,t):
        if t=="B": return s.i1()
        if t=="Z": return s.bytes(1)[0]!=0
        if t=="C": return chr(s.u2())
        if t=="S": return struct.unpack(">h",s.bytes(2))[0]
        if t=="I": return s.i4()
        if t=="J": return struct.unpack(">q",s.bytes(8))[0]
        if t=="F": return struct.unpack(">f",s.bytes(4))[0]
        if t=="D": return struct.unpack(">d",s.bytes(8))[0]
        raise ValueError("bad prim type %r"%t)
    def i1(s): return struct.unpack(">b",s.bytes(1))[0]
    def alloc(s,t):
        s.handle+=1
        if t is not None: s.objs[s.handle]=t
        return s.handle
    def ctx(s):
        return ".".join("%s.%s"%(c,f) for (c,f) in s.fpath)
    def decode_string(s,tc):
        if tc==TC_STRING:
            v=s.mod_utf()
            if not v.startswith("Notes:"):
                s.alloc(v)
            return v
        if tc==TC_LONGSTRING:
            n=struct.unpack(">Q",s.bytes(8))[0]; v=s.bytes(n).decode("utf-8","replace"); s.alloc(v); return v
        if tc==TC_REFERENCE:
            h=s.u4(); return s.objs.get(h)
        if tc==TC_NULL:
            return None
        raise ValueError("bad string TC 0x%02x"%tc)
    def read_type_string(s):
        return s.decode_string(s.u1())
    def read_class_desc(s):
        tc=s.u1()
        if tc==TC_REFERENCE:
            h=s.u4(); return s.objs.get(h)
        if tc==TC_CLASSDESC: return s.read_nonproxy_desc()
        if tc==TC_PROXYCLASSDESC:
            s.alloc(None)
            n=s.u4(); names=[s.mod_utf() for _ in range(n)]
            flags=s.u1(); s.skip_custom_data()
            s.events.append(("classdesc","proxy "+",".join(names),flags,-1))
            return None
        if tc==TC_NULL: return None
        raise ValueError("bad classdesc TC 0x%02x"%tc)
    def read_nonproxy_desc(s):
        cd=ClassDesc(); cd.handle=s.alloc(cd)
        cd.name=s.mod_utf(); suid=s.bytes(8); cd.flags=s.u1()
        nfields=s.u2()
        for _ in range(nfields):
            tcode=chr(s.u1()); fname=s.mod_utf(); ftype=""
            if tcode in ("L","["):
                ft=s.read_type_string()
                ftype=ft if ft else ""
            cd.fields.append((tcode,fname,ftype))
        s.events.append(("classdesc",cd.name,cd.flags,nfields))
        s.skip_custom_data()          # always present (annotation block terminates with TC_ENDBLOCKDATA)
        more=s.u1()
        if more==TC_CLASSDESC:
            cd.super_=s.read_nonproxy_desc()
        elif more in (TC_REFERENCE,):
            h=s.u4(); cd.super_=s.objs.get(h)
            if cd.super_ is None: raise ValueError("dangling super ref 0x%08x"%h)
        elif more==TC_PROXYCLASSDESC:
            s.alloc(None); n=s.u4(); [s.mod_utf() for _ in range(n)]
            flags=s.u1(); s.skip_custom_data()
        elif more==TC_NULL:
            pass
        else:
            raise ValueError("bad super byte 0x%02x"%more)
        return cd
    def skip_custom_data(s):
        cnt=0
        while True:
            b=s.u1()
            if b==TC_ENDBLOCKDATA: return
            if b==TC_BLOCKDATA: s.bytes(s.u1())
            elif b==TC_BLOCKDATALONG: s.bytes(s.i4())
            elif b==TC_RESET: s.handle=BASE_HANDLE; s.objs.clear()
            else:
                s.read_object_tc(b, record=False)
                cnt+=1
                if cnt>100000: raise ValueError("runaway annotations")
    def read_object_tc(s,tc,record=True):
        if tc==TC_OBJECT: return s.read_object_body(record)
        if tc==TC_REFERENCE:
            h=s.u4(); return s.objs.get(h)
        if tc in (TC_STRING,TC_LONGSTRING):
            v=s.decode_string(tc)
            if record: s.events.append(("string",v,s.ctx()))
            return v
        if tc==TC_ARRAY: return s.read_array(record)
        if tc==TC_CLASS:
            return s.read_class_desc()
        if tc==TC_ENUM:
            cd=s.read_class_desc()
            name=s.decode_string(s.u1())
            s.alloc(None)
            if record: s.events.append(("enum",cd.name if cd else None,name,s.ctx()))
            return name
        if tc==TC_NULL: return None
        if tc==TC_BLOCKDATA: return s.bytes(s.u1())
        if tc==TC_BLOCKDATALONG: return s.bytes(s.i4())
        if tc==TC_EXCEPTION:
            return s.read_object_tc(s.u1(),record)
        if tc==TC_RESET:
            s.handle=BASE_HANDLE; s.objs.clear(); return None
        raise ValueError("bad object TC 0x%02x"%tc)
    def read_object(s,record=True):
        tc=s.u1(); return s.read_object_tc(tc,record)
    def read_object_body(s,record):
        start=s.pos
        cd=s.read_class_desc()
        if cd is None: return None
        s.alloc(None)
        prev=s.cur; s.cur=cd.name
        if record: s.events.append(("object",cd.name,s.ctx()))
        try:
            ext = cd.flags & (SC_EXTERNALIZABLE|SC_BLOCKDATA) or (cd.flags & SC_SERIALIZABLE)==0 and cd.flags & SC_WRITE_METHOD
            for c in cd.chain():
                if c.flags & (SC_EXTERNALIZABLE|SC_BLOCKDATA):
                    s.skip_custom_data()
                    continue
                prims=[(t,n) for (t,n,f) in c.fields if t not in ("L","[")]
                objs=[(t,n,f) for (t,n,f) in c.fields if t in ("L","[")]
                for (t,n) in prims:
                    v=s.read_prim(t)
                    if c.name in s.peek: s.events.append(("prim",n,v,s.ctx()))
                for (t,n,f) in objs:
                    s.fpath.append((c.name,n))
                    try:
                        s.read_object()
                    finally:
                        s.fpath.pop()
                if c.flags & SC_WRITE_METHOD:
                    s.skip_custom_data()
        finally:
            s.cur=prev
        if record: s.events[-1] = ("object",cd.name,start,"->",s.pos)
        return cd
    def read_array(s,record):
        name="" 
        cd=s.read_class_desc()
        name=cd.name if cd else "?"
        if name.startswith("[[") or (name.startswith("[") and name[1]=="["):
            # nested (2D+) arrays: length = number of inner arrays, each read as an object
            n=s.i4()
            if n<0: raise ValueError("negative array len")
            s.alloc(None)
            if record: s.events.append(("objarray",name,n,s.ctx()))
            for i in range(n):
                s.fpath.append(("%s[%d]"%(name,i),""))
                try: s.read_object()
                finally: s.fpath.pop()
            return None
        n=s.i4()
        if n<0: raise ValueError("negative array len")
        if name.endswith("D"):
            data=struct.unpack(">%dd"%n,s.bytes(8*n)); s.alloc(None)
            if record: s.events.append(("arrdata","[D",len(data),data,s.ctx()))
            return data
        if name.endswith("F"):
            data=struct.unpack(">%df"%n,s.bytes(4*n)); s.alloc(None)
            if record: s.events.append(("arrdata","[F",len(data),data,s.ctx()))
            return data
        if name.endswith("I"):
            raw=s.bytes(4*n); s.alloc(None)
            if record: s.events.append(("arri","[I",n,struct.unpack(">%di"%n,raw),s.ctx()))
            return raw
        if name.endswith("S"):
            raw=s.bytes(2*n); s.alloc(None); return raw
        if name.endswith("B"):
            raw=s.bytes(n); s.alloc(None); return raw
        if name.endswith("Z"):
            raw=s.bytes(n); s.alloc(None); return raw
        if name.endswith("J"):
            raw=s.bytes(8*n); s.alloc(None); return raw
        # object array
        s.alloc(None)
        if record: s.events.append(("objarray",name,n,s.ctx()))
        for i in range(n):
            s.fpath.append(("%s[%d]"%(name,i),""))
            try: s.read_object()
            finally: s.fpath.pop()
        return None
    def run(s):
        if s.d[:2]!=MAGIC or s.d[2:4]!=VERSION: raise ValueError("bad header")
        s.pos=4
        while s.pos<len(s.d):
            try:
                s.read_object()
            except EOFError:
                break
            except Exception as e:
                raise RuntimeError("failed at byte %d/%d while in %s"%(s.pos,len(s.d),getattr(s,"cur",None))) from e
        return s.events

if __name__=="__main__":
    path=sys.argv[1]
    r=Reader(open(path,"rb").read())
    r.peek={"roomeqwizard.MeasData","roomeqwizard.CalData"}
    every = getattr(sys,'flags',None) if False else False
    try:
        evs=r.run()
    except Exception as e:
        print("FAIL:",e)
        evs=r.events
        print("-- last events (offset of failure %d) --"%r.pos)
        for e_ in evs[-60:]:
            print(e_)
        sys.exit(2)
    for e in evs:
        if e[0]=="classdesc": print("class %-42s flags=0x%02x nf=%d"%(e[1],e[2],e[3]))
        elif e[0]=="object": print("   obj %s"%(e[1],))
        elif e[0]=="arrdata":
            d=e[3]; print("   arr %-3s len=%-5d @%s [0]=%10.4f [last]=%10.4f"%(e[1],e[2],e[4],d[0],d[-1]))
        elif e[0]=="arri":
            d=e[3]; print("   arri %-3s len=%-5d @%s [0]=%d [last]=%d"%(e[1],e[2],e[4],d[0],d[-1]))
        elif e[0]=="objarray": print("   objarr %s len=%d @%s"%(e[1],e[2],e[3]))
        elif e[0]=="string": print("   str %r"%(e[1][:110],))
        elif e[0]=="enum": print("   enum %s = %s"%(e[1],e[2]))
        elif e[0]=="prim": print("   prim %s=%r @%s"%(e[1],e[2],e[3]))