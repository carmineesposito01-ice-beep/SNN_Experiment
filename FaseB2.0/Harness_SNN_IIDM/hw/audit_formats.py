import io,re,ast,sys
# Conta gli specificatori DOPO aver tolto gli escape '%%': altrimenti "%% del" viene letto come "% d".
SPEC=re.compile(r'%[-+ #0-9.*]*[diufgGeEsxXcr]')
def nspec(s): return len(SPEC.findall(s.replace('%%','')))
bad=[]
for p in sys.argv[1:]:
    tree=ast.parse(io.open(p,encoding='utf-8').read())
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('a','print') and node.args:
            arg=node.args[0]
            if isinstance(arg,ast.BinOp) and isinstance(arg.op,ast.Mod) and isinstance(arg.left,ast.Constant) \
               and isinstance(arg.left.value,str):
                s=arg.left.value; r=arg.right
                na=len(r.elts) if isinstance(r,ast.Tuple) else 1
                ns=nspec(s)
                if ns!=na: bad.append((p,node.lineno,ns,na,s[:64]))
print('disallineamenti: %d' % len(bad))
for p,ln,ns,na,s in bad:
    print('  %s:%d  %d specificatori / %d argomenti  |  %s...' % (p.split('/')[-1],ln,ns,na,s))
sys.exit(1 if bad else 0)
