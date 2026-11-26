// Imported calibration proposals and the editable draft for the current position.
let reviewQueue={entries:[],index:0,approved:[],examine:false},draftPosition='';
function queued(){return reviewQueue.entries.length>0&&!reviewQueue.examine}
function queueItem(){return queued()?reviewQueue.entries[reviewQueue.index]:null}
function matchesScan(spec,scan){
 return !spec||scan==null||spec.split(',').some(part=>{const [a,b=a]=part.split('~').map(Number);return scan>=a&&scan<=b});
}
function queueDraft(ant,scan){
 if(!reviewQueue.entries.length)return;
 const pos=queued()?'item'+reviewQueue.index:JSON.stringify([ant,scan]);
 if(pos===draftPosition)return;
 draftPosition=pos;
 const items=queued()?[queueItem()].filter(Boolean):reviewQueue.entries.filter(e=>e.ant===ant&&matchesScan(e.scan,scan)&&!reviewQueue.approved.includes(e.text));
 $('cmd').value=[...new Set(items.map(e=>e.text))].join('\n');
 $('reason').value=[...new Set(items.map(e=>e.reason).filter(Boolean))].join('\n');
}
function reviewBanner(){
 const q=reviewQueue;
 $('progress').textContent=q.entries.length?(queued()?'Command '+(q.index+1)+' of '+q.entries.length:'Examining all data · '+q.entries.length+' imported commands')+
 (q.excluded?' · '+q.excluded+' for unloaded tables':''):'';
}
async function syncReview(){
 const s=await api('state');reviewQueue=s.review;
 if(queued()&&!queueItem()){document.body.replaceChildren();const title=document.createElement('h1');title.textContent='Review complete';const info=document.createElement('p');info.textContent='Approved commands: '+s.out;const close=document.createElement('button');close.textContent='Exit';close.onclick=async()=>{await api('exit');close.disabled=true};document.body.append(title,info,close);return false}
 reviewBanner();return true;
}
