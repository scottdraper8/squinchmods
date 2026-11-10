const allRecords=window.NMS_GLOSSARY_DATA||[];
const search=document.querySelector('#search'),kind=document.querySelector('#kind'),category=document.querySelector('#category'),rarity=document.querySelector('#rarity'),sort=document.querySelector('#sort'),glossary=document.querySelector('#glossary'),status=document.querySelector('#status'),loadMore=document.querySelector('#load-more'),sentinel=document.querySelector('#scroll-sentinel');
const indexed=allRecords.map(item=>({item,search:[item.name,item.id,item.kind,item.category,item.categoryKey,item.rarity,item.subtitle,item.description,item.secondary,item.nameKey,item.descriptionKey,...item.tags].join(' ').toLocaleLowerCase()}));
const batchSize=40;
let rendered=0,visible=[];

function addOptions(control,values){for(const name of values){const option=document.createElement('option');option.value=name;option.textContent=name;control.append(option)}}
addOptions(kind,[...new Set(allRecords.map(item=>item.kind))].sort((a,b)=>a.localeCompare(b)));
addOptions(category,[...new Set(allRecords.map(item=>item.category))].sort((a,b)=>a.localeCompare(b)));
addOptions(rarity,[...new Set(allRecords.map(item=>item.rarity))].sort((a,b)=>a.localeCompare(b)));

function copyText(value,button){navigator.clipboard.writeText(value).then(()=>copied(button)).catch(()=>{const area=document.createElement('textarea');area.value=value;document.body.append(area);area.select();document.execCommand('copy');area.remove();copied(button)})}
function copied(button){const old=button.textContent;button.textContent='Copied';setTimeout(()=>button.textContent=old,900)}
function element(name,className,text){const node=document.createElement(name);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node}
function definition(list,label,value){if(value===null||value===undefined||value==='')return;const wrapper=element('div');wrapper.append(element('dt','',label),element('dd','',value));list.append(wrapper)}

function card(item){
  const article=element('article','glossary-card');
  if(item.colour)article.style.setProperty('--item-colour',item.colour);
  const visual=element('div','glossary-icon');
  if(item.preview){const image=document.createElement('img');image.loading='lazy';image.src=item.preview;image.alt='';image.addEventListener('error',()=>{image.remove();visual.append(element('span','icon-fallback',item.name.slice(0,1)))},{once:true});visual.append(image)}else visual.append(element('span','icon-fallback',item.name.slice(0,1)));
  const body=element('div','glossary-body'),badges=element('div','badges');
  badges.append(element('span','badge kind-badge',item.kind),element('span','badge',item.category));
  const heading=element('h2','',item.name),id=element('code','item-id',item.id);
  const titleRow=element('div','glossary-title');titleRow.append(heading,id);
  body.append(badges,titleRow);
  if(item.subtitle)body.append(element('p','glossary-subtitle',item.subtitle));
  if(item.description)body.append(element('p','glossary-description',item.description));
  if(item.tags.length){const tags=element('ul','tag-list');for(const tag of item.tags)tags.append(element('li','',tag));body.append(tags)}
  const facts=element('dl','item-facts');
  definition(facts,'Rarity / quality',item.rarity);
  definition(facts,'Subtype',item.secondary);
  definition(facts,'Base value',item.baseValue===null?null:Number(item.baseValue).toLocaleString());
  definition(facts,'Level',item.level);
  definition(facts,'Stack multiplier',item.stackMultiplier);
  body.append(facts);
  const actions=element('div','item-actions'),copy=document.createElement('button');copy.type='button';copy.textContent='Copy internal ID';copy.addEventListener('click',()=>copyText(item.id,copy));
  const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Game metadata';details.append(summary);
  const metadata=element('dl','game-metadata');definition(metadata,'Source table',item.source);definition(metadata,'Category key',item.categoryKey);definition(metadata,'Name key',item.nameKey);definition(metadata,'Description key',item.descriptionKey);definition(metadata,'Icon path',item.icon);details.append(metadata);actions.append(copy,details);body.append(actions);
  article.append(visual,body);return article;
}

const comparators={
  name:(a,b)=>a.name.localeCompare(b.name)||a.id.localeCompare(b.id),
  id:(a,b)=>a.id.localeCompare(b.id)||a.name.localeCompare(b.name),
  kind:(a,b)=>a.kind.localeCompare(b.kind)||a.name.localeCompare(b.name),
  category:(a,b)=>a.category.localeCompare(b.category)||a.name.localeCompare(b.name)
};
function remember(){try{const url=new URL(location.href);for(const [key,control] of [['q',search],['kind',kind],['category',category],['rarity',rarity],['sort',sort]]){if(control.value)url.searchParams.set(key,control.value);else url.searchParams.delete(key)}url.searchParams.delete('page');url.searchParams.delete('size');history.replaceState(null,'',url)}catch{}}
function updateStatus(){status.textContent='Showing '+rendered.toLocaleString()+' of '+visible.length.toLocaleString()+' matching entries · '+allRecords.length.toLocaleString()+' total';const complete=rendered>=visible.length;loadMore.hidden=complete;sentinel.hidden=complete}
function appendNext(){if(rendered>=visible.length)return;const end=Math.min(rendered+batchSize,visible.length),fragment=document.createDocumentFragment();for(const item of visible.slice(rendered,end))fragment.append(card(item));glossary.append(fragment);rendered=end;updateStatus()}
function draw(){
  const tokens=search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  visible=indexed.filter(({item,search:haystack})=>tokens.every(token=>haystack.includes(token))&&(!kind.value||item.kind===kind.value)&&(!category.value||item.category===category.value)&&(!rarity.value||item.rarity===rarity.value)).map(({item})=>item).sort(comparators[sort.value]);
  glossary.replaceChildren();rendered=0;
  if(!visible.length){glossary.append(element('p','empty','No item or technology entries match these filters.'));updateStatus();remember();return}
  appendNext();remember();
}
function restore(){const values=new URL(location.href).searchParams;for(const [key,control] of [['q',search],['kind',kind],['category',category],['rarity',rarity],['sort',sort]]){const selected=values.get(key);if(selected&&(control===search||[...control.options].some(option=>option.value===selected)))control.value=selected}}
let timer;search.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(draw,120)});for(const control of [kind,category,rarity,sort])control.addEventListener('change',draw);loadMore.addEventListener('click',appendNext);
new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting))appendNext()},{rootMargin:'900px 0px'}).observe(sentinel);
restore();draw();
