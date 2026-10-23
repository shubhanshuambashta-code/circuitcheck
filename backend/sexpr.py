"""Bounded concrete-syntax reader for documented KiCad S-expressions.

Nodes retain byte/character spans. Repairs replace one numeric atom, preserving every
other character. This is a structured parse, never a regex rewrite.
Spec: https://dev-docs.kicad.org/en/file-formats/sexpr-intro/
"""
from dataclasses import dataclass, field
import json

@dataclass
class Node:
    start: int
    end: int
    value: str | None = None
    children: list = field(default_factory=list)

    @property
    def tag(self):
        return self.children[0].value if self.children else self.value

    def all(self, tag):
        return [n for n in self.children if n.children and n.tag == tag]

    def get(self, tag):
        return next(iter(self.all(tag)), None)

    def arg(self, index=1, default=None):
        return self.children[index].value if len(self.children)>index else default

def parse(text: str):
    i, count = 0, 0
    def read(depth=0):
        nonlocal i, count
        count += 1
        if depth > 128 or count > 1000000:
            raise ValueError('Design exceeds parser limits')
        def skip():
            nonlocal i
            while i<len(text):
                if text[i].isspace(): i+=1
                elif text[i]=='#':
                    while i<len(text) and text[i] not in '\r\n': i+=1
                else: break
        skip()
        if i>=len(text): raise ValueError('Unexpected end of design')
        start = i
        if text[i]=='(':
            i += 1
            items=[]
            while True:
                skip()
                if i>=len(text): raise ValueError('Unclosed S-expression')
                if text[i]==')':
                    i += 1
                    return Node(start,i,children=items)
                items.append(read(depth+1))
        if text[i]==')': raise ValueError('Unexpected closing parenthesis')
        if text[i]=='"':
            i += 1
            chars=[]
            while i<len(text) and text[i]!='"':
                if text[i]=='\\':
                    i += 1
                    if i>=len(text): raise ValueError('Invalid string escape')
                    chars.append({'n':'\n','r':'\r','t':'\t'}.get(text[i],text[i]))
                else: chars.append(text[i])
                i += 1
            if i>=len(text): raise ValueError('Unterminated string')
            i += 1
            return Node(start,i,''.join(chars))
        while i<len(text) and not text[i].isspace() and text[i] not in '()': i += 1
        return Node(start,i,text[start:i])
    result=read()
    if text[i:].strip(): raise ValueError('Unexpected data after design')
    return result

def number(node, tag, index=1):
    n=node.get(tag)
    return float(n.arg(index)) if n else None

def tracks(text):
    root=parse(text)
    if root.tag!='kicad_pcb': raise ValueError('Expected a KiCad board')
    result=[]
    for n in root.all('segment'):
        uid=n.get('uuid') or n.get('tstamp')
        if not uid: continue
        result.append({'id':uid.arg(), 'width':number(n,'width'), 'layer':n.get('layer').arg(),
                       'start':[number(n,'start'),number(n,'start',2)], 'end':[number(n,'end'),number(n,'end',2)],
                       'net':n.get('net').arg() if n.get('net') else None,'node':n})
    return result

def change_width(text, object_id, expected, target):
    matches=[t for t in tracks(text) if t['id']==object_id]
    if len(matches)!=1: raise ValueError('Exact track UUID could not be resolved uniquely')
    track=matches[0]
    if abs(track['width']-expected)>1e-9: raise ValueError('Track width changed since analysis')
    if not (0 < expected < target <= 10): raise ValueError('Unsupported track width change')
    n=track['node'].get('width').children[1]
    result=text[:n.start]+format(target,'.8g')+text[n.end:]
    parse(result)
    return result

