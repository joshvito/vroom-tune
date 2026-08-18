import javaobj, sys, time

path = "/home/josh/Downloads/2020-ford-ranger-rta-measurements-bb.mdat"

with open(path, "rb") as f:
    data = f.read()

print("file size:", len(data))
t0 = time.time()
obj = javaobj.loads(data)
print("parsed in %.1fs" % (time.time() - t0))
print("top type:", type(obj))

def describe(o, depth=0, maxdepth=6, key="root"):
    indent = "  " * depth
    if depth > maxdepth:
        print(indent + "..." )
        return
    t = type(o)
    print(f"{indent}[{key}] {t.__module__}.{t.__name__}", end="")
    if hasattr(o, "name"):
        print(" name=%r" % getattr(o, "name"), end="")
    if hasattr(o, "classdesc"):
        cd = o.classdesc.name if hasattr(o.classdesc, "name") else o.classdesc
        print(" classdesc=%r" % cd, end="")
    print()
    if t is dict or (hasattr(o, "__dict__") and not isinstance(o, (int,float,str,bytes,list,tuple))):
        try:
            d = o.__dict__ if hasattr(o, "__dict__") else dict(o)
        except Exception:
            d = {}
        for k, v in list(d.items())[:14]:
            describe(v, depth + 1, maxdepth, k)

describe(obj)