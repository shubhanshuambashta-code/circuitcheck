import {useEffect,useRef,type ReactNode} from 'react';
import {X} from 'lucide-react';
export default function Modal({title,onClose,children,wide=false}:{title:string;onClose:()=>void;children:ReactNode;wide?:boolean}){
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{ref.current?.showModal();return()=>{ref.current?.close()}},[]);
 return <dialog ref={ref} className={`modal ${wide?'wide':''}`} onCancel={onClose} onClick={e=>{if(e.target===ref.current){const r=ref.current.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose()}}} aria-label={title}><div className="modal-heading"><h2>{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={19}/></button></div>{children}</dialog>
}
