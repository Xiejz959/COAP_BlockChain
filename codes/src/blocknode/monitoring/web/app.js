'use strict';
const $ = id => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
let current = null;
let selection = null;
let graphVersion = '';
let followHead = true;
const expandedEvents = new Set();
const number = value => new Intl.NumberFormat('en-US').format(value);
const short = hash => hash.slice(0, 8) + '…' + hash.slice(-4);
const clock = value => new Date(value * 1000).toLocaleTimeString('zh-CN', {hour12:false});
function svg(tag, attributes, text) {
  const element = document.createElementNS(NS, tag);
  for (const [name,value] of Object.entries(attributes)) element.setAttribute(name,value);
  if (text !== undefined) element.textContent = text;
  return element;
}
function inspect(hash) {
  const block = current.blocks.find(item => item.hash === hash);
  if (!block) return;
  selection = hash;
  $('block-height').textContent = '# ' + String(block.height).padStart(4,'0');
  $('block-kind').textContent = block.height === 0 ? 'GENESIS' : block.canonical ? 'CANONICAL' : 'SIDE BRANCH';
  $('block-kind').classList.toggle('side', !block.canonical);
  for (const [id,value] of Object.entries({'block-hash':block.hash,'block-parent':block.parent,'block-node':block.node_id,'block-nonce':block.nonce,'block-work':number(BigInt(block.work))})) $(id).textContent = value;
  document.querySelectorAll('.block-card').forEach(card => card.classList.toggle('selected',card.dataset.hash === hash));
}
function drawChain(state) {
  const version = state.blocks.map(block => block.hash+block.canonical).join('');
  if (version === graphVersion) { inspect(selection); return; }
  graphVersion = version;
  const root = $('chain-graph');
  root.replaceChildren();
  const blocks = state.blocks;
  const max = Math.max(...blocks.map(block=>block.height));
  const width = Math.max(620,(max-state.visible_from+1)*128+72);
  const lanes = new Map(); let laneCount = 0;
  for (const block of blocks) lanes.set(block.hash, block.canonical ? 0 : lanes.has(block.parent) && lanes.get(block.parent)>0 ? lanes.get(block.parent) : ++laneCount);
  const height = Math.max(230, 156+laneCount*86);
  root.setAttribute('width',width);root.setAttribute('height',height);root.setAttribute('viewBox',`0 0 ${width} ${height}`);
  const position = block => ({x:36+(block.height-state.visible_from)*128,y:76+lanes.get(block.hash)*86});
  const byHash = new Map(blocks.map(block=>[block.hash,block]));
  for (let h=state.visible_from;h<=max;h++) {
    const x=36+(h-state.visible_from)*128;
    root.append(svg('text',{x:x+45,y:25,'text-anchor':'middle',class:'axis-label'},'HEIGHT '+String(h).padStart(3,'0')));
  }
  for (const block of blocks) {
    const p = position(block); const parent=byHash.get(block.parent);
    if (parent) {
      const a=position(parent);
      root.append(svg('path',{d:`M ${a.x+96} ${a.y+27} C ${a.x+112} ${a.y+27}, ${p.x-16} ${p.y+27}, ${p.x} ${p.y+27}`,class:'chain-line'+(block.canonical?'':' side')}));
    }
  }
  for (const block of blocks) {
    const p=position(block);
    const card=svg('g',{transform:`translate(${p.x} ${p.y})`,class:'block-card'+(block.canonical?'':' side'),tabindex:0,role:'button','aria-label':`区块 ${block.height}，${block.canonical?'当前链':'旁支'}`});
    card.dataset.hash=block.hash;
    card.append(svg('rect',{width:96,height:56,rx:7}),svg('text',{x:12,y:23},block.height===0?'GENESIS':'# '+String(block.height).padStart(4,'0')),svg('text',{x:12,y:42,class:'hash-label'},block.hash.slice(0,9)));
    card.addEventListener('click',()=>{followHead=false;inspect(block.hash);});
    card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();followHead=false;inspect(block.hash);}});
    root.append(card);
    if(block.hash===state.head)root.append(svg('text',{x:p.x+48,y:p.y-13,'text-anchor':'middle',class:'tip-label'},'SELECTED HEAD'));
  }
  if (followHead || !blocks.some(block=>block.hash===selection)) selection=state.head;
  inspect(selection);
  if (selection===state.head) $('chain-scroll').scrollLeft=width;
}
function drawChart(samples) {
  const root=$('rate-chart');root.replaceChildren();
  for(let i=0;i<4;i++)root.append(svg('line',{x1:0,y1:15+i*40,x2:600,y2:15+i*40,stroke:'#223440','stroke-dasharray':'3 5'}));
  $('chart-empty').hidden=samples.length>0;
  $('chart-empty').style.display=samples.length?'none':'flex';
  $('sample-count').textContent=samples.length+' 个搜索样本';
  if(!samples.length)return;
  const peak=Math.max(...samples.map(item=>item.rate))*1.2;
  const points=samples.map((item,i)=>({x:12+i*576/Math.max(samples.length-1,1),y:135-item.rate/peak*115}));
  const line=points.map((p,i)=>(i?'L':'M')+p.x+' '+p.y).join(' ');
  const defs=svg('defs',{});const gradient=svg('linearGradient',{id:'area',x1:0,y1:0,x2:0,y2:1});gradient.append(svg('stop',{offset:'0%','stop-color':'#83decf','stop-opacity':'.20'}),svg('stop',{offset:'100%','stop-color':'#83decf','stop-opacity':'0'}));defs.append(gradient);root.append(defs);
  root.append(svg('path',{d:line+` L ${points.at(-1).x} 148 L 12 148 Z`,fill:'url(#area)'}),svg('path',{d:line,fill:'none',stroke:'#83decf','stroke-width':2,'stroke-linejoin':'round'}));
  const last=points.at(-1);root.append(svg('circle',{cx:last.x,cy:last.y,r:4,fill:'#c8fff3',stroke:'#183b39','stroke-width':3}));
  $('sample-first').textContent=clock(samples[0].time);$('sample-last').textContent=clock(samples.at(-1).time);
}
function render(state) {
  current=state;
  $('identity').textContent=short(state.node_id);$('endpoint').textContent=state.listen;$('local-short').textContent=state.node_id.slice(0,8);
  $('height').textContent=number(state.height);$('peer-count').textContent=state.peers.length;
  $('peer-note').textContent=state.peers.length?'TCP 连接已建立 · 本节点视角':'独立运行 · 等待其他节点接入';
  $('compute-state').textContent=state.computing?'正在计算':'验证与同步';
  $('compute-note').textContent=`本次进程已生成 ${state.local_blocks} 个有效区块`;
  $('rate').replaceChildren();
  if(state.last_rate===null){$('rate').textContent='—';$('chart-rate').textContent='—';}
  else{const rate=(state.last_rate/1e6).toFixed(2);$('rate').append(document.createTextNode(rate));const unit=document.createElement('small');unit.textContent='MH/s';$('rate').append(unit);$('chart-rate').textContent=rate+' MH/s';}
  $('chart-caption').textContent=state.samples.length?'每次完成搜索的平均速率 · 本次进程':'本次进程尚未完成 PoW 搜索';
  $('branch-count').textContent=state.side_blocks+' 个旁支块';
  $('chain-range').textContent=`HEIGHT ${state.visible_from} — ${state.height} / ${state.known_blocks} VERIFIED BLOCKS`;
  $('head').textContent=state.head;$('head').title=state.head;
  drawChain(state);drawChart(state.samples);
  const peers=$('peer-list');peers.replaceChildren();
  if(!state.peers.length){const empty=document.createElement('p');empty.className='empty-state';empty.textContent='当前没有已完成握手的连接';peers.append(empty);}
  for(const peer of state.peers){const card=document.createElement('div');card.className='peer-item';const top=document.createElement('div');top.className='peer-item-top';const name=document.createElement('span');name.textContent=peer.node_id.slice(0,8);const status=document.createElement('span');status.textContent=peer.syncing?'SYNCING':'CONNECTED';top.append(name,status);const detail=document.createElement('p');detail.textContent=`${peer.address} · 最近通告高度 ${peer.height===null?'待验证':peer.height}`;const seen=document.createElement('p');seen.textContent=`${short(peer.head)} · ${clock(peer.last_seen)}`;card.append(top,detail,seen);peers.append(card);}
  const events=$('event-list');events.replaceChildren();
  for(const event of state.events){
    const row=document.createElement(event.block_hash?'summary':'div');row.className='event-row';
    const time=document.createElement('span');time.className='event-time';time.textContent=clock(event.time);
    const kind=document.createElement('span');kind.className='event-kind'+(['REORG','DISCONNECTED'].includes(event.kind)?' warn':'');kind.textContent=event.kind;
    const detail=document.createElement('span');detail.textContent=event.detail+(event.block_hash?'  ↗':'');row.append(time,kind,detail);
    if(event.block_hash){const entry=document.createElement('details');const key=event.time+':'+event.kind;entry.open=expandedEvents.has(key);entry.addEventListener('toggle',()=>{if(entry.open)expandedEvents.add(key);else expandedEvents.delete(key);});
      const expanded=document.createElement('div');expanded.className='event-detail';const label=document.createElement('span');label.textContent='BLOCK HASH';const hash=document.createElement('code');hash.textContent=event.block_hash;expanded.append(label,hash);entry.append(row,expanded);events.append(entry);
    }else events.append(row);
  }
  $('updated').textContent='UPDATED '+clock(state.updated_at);
}
async function refresh(){
  try{const response=await fetch('/api/state',{cache:'no-store'});if(!response.ok)throw new Error('HTTP '+response.status);render(await response.json());$('connection').classList.remove('offline');$('connection').replaceChildren();const light=document.createElement('i');$('connection').append(light,document.createTextNode('节点已连接'));}
  catch(error){$('connection').classList.add('offline');$('connection').replaceChildren();const light=document.createElement('i');$('connection').append(light,document.createTextNode('数据连接中断'));$('updated').textContent='更新失败 · '+error.message;}
  window.setTimeout(refresh,1000);
}
refresh();
