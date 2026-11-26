"""Read calibration proposals as data, retaining the scope of each CASA call."""
import ast
import codeop
import hashlib
from pathlib import Path
import re

import numpy as np
from selections import command, matches, report_pages

ALIASES = {'complx':'bpass_complx.t','scalar':'bpass_scalar.t','vis':'ff_sb.t'}


def scan_mask(scans, spec):
    if not spec:
        return np.ones(len(scans),bool)
    result=np.zeros(len(scans),bool)
    for term in spec.split(','):
        result |= matches(scans,term)
    return result


def read_calls(text, pdf):
    lines=iter(text.splitlines())
    reason=''
    for line in lines:
        line=line.strip()
        if not line:
            continue
        if not re.match(r'^flagdata\s*\(',line):
            if pdf:
                reason=line if len(line)<200 and not line.startswith(('#','copytree','from ','vis =')) else ''
            elif line.startswith('#'):
                reason=(reason+'\n'+line[1:].strip()).strip()
            else:
                raise ValueError('Expected literal flagdata calls or comments in the ASCII file')
            continue
        while codeop.compile_command(line,symbol='eval') is None:
            try:
                line+='\n'+next(lines)
            except StopIteration:
                raise ValueError('Incomplete flagdata call in input')
        call=ast.parse(line,mode='eval').body
        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name) or call.func.id!='flagdata' or call.args:
            raise ValueError('Expected literal CASA keyword arguments')
        k={}
        for kw in call.keywords:
            if not kw.arg or kw.arg in k:
                raise ValueError('Invalid or repeated flagdata argument')
            if pdf and kw.arg=='vis' and isinstance(kw.value,ast.Name) and kw.value.id in ALIASES:
                k['vis']=ALIASES[kw.value.id]
            else:
                k[kw.arg]=ast.literal_eval(kw.value)
        yield k,reason
        reason=''


class ImportedReview:
    def __init__(self,args,paths,output,validate):
        self.entries=[]
        self.identity={}
        self.excluded=0
        pdf=getattr(args,'pdf',None)
        source=pdf or getattr(args,'commands',None)
        self.examine=bool(source and getattr(args,'examine',False))
        if not source:
            return
        src=Path(source).resolve()
        if src==output.resolve():
            raise ValueError('Choose separate input and output files')
        self.identity={'proposals':hashlib.sha256(src.read_bytes()).hexdigest(),'examine':self.examine}
        pages=report_pages(src) if pdf else [src.read_text(encoding='utf-8-sig')]
        tables={p.name:str(p) for p in paths}
        for page in pages:
            for k,reason in read_calls(page,bool(pdf)):
                name=Path(k['vis']).name
                if name not in tables:
                    if name in ('bpass_complx.t','bpass_scalar.t') and set(tables)<=set(('bpass_complx.t','bpass_scalar.t')):
                        self.excluded+=1
                        continue
                    raise ValueError(f'Command target {name} does not match a loaded table')
                k['vis']=tables[name]
                text=command(k)
                validate(text)
                self.entries.append(dict(text=text,reason=reason,ant=k['antenna'].removesuffix('&&&'),
                                         scan=k.get('scan',''),table=name,parameter=k.get('correlation','')))
        if not self.entries:
            raise ValueError('No active flagdata calls for the loaded tables')

    def status(self,review):
        steps=review.log.data['steps']
        return dict(entries=self.entries,index=len(steps),examine=self.examine,excluded=self.excluded,
                    approved=[command(k) for s in steps for k in s.get('calls',[])])

    def check(self,review,q):
        if self.entries and not self.examine:
            index=len(review.log.data['steps'])
            if q.get('index')!=index or index>=len(self.entries):
                raise ValueError('Review position changed. Reload the widget.')
