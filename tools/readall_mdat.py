import javaobj, sys, time, io

path = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: python readall_mdat.py <input.mdat>")
buff = open(path, "rb").read()

def read_all():
    fd = io.BytesIO(buff)
    objs = []
    total = len(buff)
    while fd.tell() < total - 2:
        try:
            o = javaobj.load(fd)
            objs.append(o)
        except Exception as e:
            print("stop at", fd.tell(), "err:", e)
            break
        if fd.tell() == 0:
            break
    return objs

objs = read_all()
print("num objects:", len(objs))
for i, o in enumerate(objs):
    print(i, type(o), getattr(o, '__dict__', {}).get('classdesc', ''), repr(str(o))[:80])