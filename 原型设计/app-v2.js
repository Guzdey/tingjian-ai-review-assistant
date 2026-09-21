const sceneOptions=[
  {code:'commute',label:'通勤'},
  {code:'meeting',label:'视频会议'},
  {code:'exercise',label:'运动'},
  {code:'long_wear',label:'长时间佩戴'},
];
const aspectOptions=[
  {code:'comfort',label:'舒适度'},
  {code:'battery',label:'续航'},
  {code:'sound_quality',label:'音质'},
  {code:'noise_cancellation',label:'降噪'},
  {code:'call_quality',label:'通话清晰'},
  {code:'connection',label:'连接稳定'},
];
const sceneLabels=Object.fromEntries([...sceneOptions,{code:'general',label:'日常使用'}].map(item=>[item.code,item.label]));
const aspectLabels=Object.fromEntries(aspectOptions.map(item=>[item.code,item.label]));
const verdictLabels={good_fit:'较匹配',uncertain:'不确定',poor_fit:'较不匹配',unavailable:'无法判断'};
const strengthLabels={insufficient:'证据不足',weak:'证据较弱',medium:'证据中等',strong:'证据较强'};
const stanceLabels={support:'支持',oppose:'反对',mixed:'观点混合'};
const productIds=['demo-tws-a','demo-tws-b'];

const state={
  scenes:new Set(['commute','meeting']),
  aspects:new Set(['call_quality','connection']),
  freeText:'每天地铁通勤约1小时，也会在办公室开视频会议，不希望频繁断连。',
  parsedNeed:null,
  parseMode:null,
  report:null,
  comparison:null,
  evidence:[],
  selectedAspect:'sound_quality',
  evidenceFilter:'all',
  compareProduct:null,
  health:{status:'checking',mode:null,model_configured:false,is_demo_cache:true,evidence_source:'demo_cache',evidence_loaded:0},
  request:{busy:false,operation:null,error:''},
  demoState:'insufficient',
};

const screens={};
const navTop=(back='product',right='⋯')=>`<div class="topbar"><button class="back" aria-label="返回" onclick="go('${back}')">‹</button><div class="brand">听<i>荐</i></div><button class="ghost" aria-label="更多">${right}</button></div>`;
const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const safeArray=value=>Array.isArray(value)?value:[];
const formatDate=value=>{try{return new Date(value).toLocaleString('zh-CN',{hour12:false})}catch{return ''}};
const currentNeed=()=>state.parsedNeed||localNeed();
const sceneLabel=()=>currentNeed().scenes.map(code=>sceneLabels[code]||code).join('、')||'未明确场景';
const needSummary=()=>{
  const need=currentNeed();
  const aspects=need.aspects.map(item=>aspectLabels[item.name]||item.name).join('、')||'未指定维度';
  const constraints=safeArray(need.constraints).map(item=>item.label).join('、');
  return `${sceneLabel()}；重点关注${aspects}${constraints?`；排除${constraints}`:''}`;
};

function servicePill(){
  if(state.health.status==='checking')return '<span class="service-pill cache">正在检测后端服务</span>';
  if(state.health.status!=='ok')return '<span class="service-pill offline">前端离线演示</span>';
  if(state.health.mode==='qwen'&&!state.health.is_demo_cache)return '<span class="service-pill">真实评论证据 · 千问已连接</span>';
  if(!state.health.is_demo_cache)return '<span class="service-pill">真实评论派生数据 · 本地规则</span>';
  if(state.health.mode==='qwen')return '<span class="service-pill cache">千问已连接 · 演示证据</span>';
  return '<span class="service-pill cache">后端已连接 · 演示缓存</span>';
}

function resultModeBanner(meta){
  if(!meta)return '<div class="runtime-banner error"><strong>结果来源未知</strong>请勿将本页内容当作真实商品结论。</div>';
  if(meta.mode==='qwen'&&!meta.is_demo_cache){
    return `<div class="runtime-banner"><strong>真实评论证据 · 千问总结</strong>模型只依据当前检索证据生成总结。生成时间：${escapeHtml(formatDate(meta.generated_at))}</div>`;
  }
  if(!meta.is_demo_cache){
    return '<div class="runtime-banner"><strong>真实评论派生证据 · 本地规则报告</strong>英文短片段来自公开匿名样本；主题、倾向和结论由规则生成，仍需人工复核。</div>';
  }
  const mode=meta.mode==='local_rules'?'后端本地规则':'前端离线降级';
  return `<div class="runtime-banner cache"><strong>演示缓存结果 · 非本次实时生成</strong>${mode}。当前片段只用于验证交互和证据结构，不代表真实购买建议。</div>`;
}

function chipButtons(group,options){
  return options.map(item=>`<button class="chip ${state[group].has(item.code)?'active':''}" aria-pressed="${state[group].has(item.code)}" onclick="toggleSelection('${group}','${item.code}')">${item.label}</button>`).join('');
}

screens.product=()=>`${navTop('product')}<div class="hero"></div><section class="content"><div class="eyebrow">匿名商品样本 · DEMO TWS A</div><h1 class="title">样本耳机 A</h1><p class="sub">首版只比较两款匿名样本。报告会分别标明模型来源与数据来源：真实评论派生、演示缓存或前端离线降级。</p>${servicePill()}<div class="rating">证据式分析 <b>保留正反观点与信息缺口</b></div><div class="price">¥ -- <small>研究型Demo不展示实时价格</small></div><div class="ai-entry"><div><h3>AI帮我判断</h3><p>从与你需求相关的评论中找证据</p></div><button class="round" aria-label="进入AI判断" onclick="go('needs')">›</button></div><button class="text-link" onclick="go('baseline')">进入普通评论基线任务 ›</button></section><nav class="bottom-nav"><b>商品</b><span>评价</span><span>参数</span><span>收藏</span></nav>`;

screens.needs=()=>`${navTop('product')}<section class="content"><div class="eyebrow">01 使用需求</div><h1 class="section-title">你准备怎么使用这副耳机</h1><p class="section-copy">场景会改变证据排序。系统先解析需求，由你确认后才开始分析。</p><div class="label">主要场景</div><div class="chips">${chipButtons('scenes',sceneOptions)}</div><div class="label">最看重什么</div><div class="chips">${chipButtons('aspects',aspectOptions)}</div><p class="hint">建议优先选择 3–4 项，报告会先展示与你最相关的证据。</p><div class="label">补充一句</div><textarea class="input" maxlength="300" oninput="state.freeText=this.value" aria-label="补充使用需求">${escapeHtml(state.freeText)}</textarea><p class="hint">最多300字。请不要填写姓名、电话或账号。</p>${state.request.error?`<div class="request-error">${escapeHtml(state.request.error)}</div>`:''}</section><button class="cta" ${state.request.busy?'disabled':''} onclick="prepareConfirmation()">${state.request.busy?'正在理解需求…':'检查AI理解'}</button>`;

screens.confirm=()=>{
  const need=currentNeed();
  return `${navTop('needs')}<section class="content"><div class="eyebrow">02 需求确认</div><h1 class="section-title">系统这样理解你的需求</h1><p class="section-copy">推断可能出错。请先检查标签，再确认分析。</p>${state.parseMode==='qwen'?'<div class="runtime-banner"><strong>AI实时解析</strong>你仍然拥有最终修改权。</div>':'<div class="runtime-banner cache"><strong>本地规则解析</strong>尚未连接真实模型，请重点检查标签是否正确。</div>'}<div class="confirm-list"><article class="confirm-card"><h3>使用场景</h3><div class="tag-row">${tagList('scenes',need.scenes)}</div></article><article class="confirm-card"><h3>关注维度</h3><div class="tag-row">${tagList('aspects',need.aspects.map(item=>item.name))}</div></article><article class="confirm-card"><h3>排除条件</h3><div class="tag-row">${tagList('constraints',need.constraints.map(item=>item.code))}</div>${need.constraints.length?'<p class="confirm-note">排除条件来自自然语言推断，属于硬性条件，需要你确认。</p>':''}</article><article class="confirm-card"><h3>原始需求</h3><p class="sub">${escapeHtml(need.raw_text)||'未填写补充说明'}</p></article></div><button class="text-link" onclick="go('needs')">返回修改原始需求</button></section><button class="cta" onclick="startAnalysis()">确认并分析</button>`;
};

screens.loading=()=>`${navTop('confirm')}<section class="loading"><div><div class="pulse"><b>AI</b></div><h2>${state.request.operation==='compare'?'正在比较两款样本':'正在整理证据'}</h2><p class="sub">解析需求 → 检索证据 → 聚合统计 → 生成报告</p><div class="steps"><div class="done">需求已确认：${escapeHtml(sceneLabel())}</div><div class="${state.request.busy?'done':''}">正在请求后端并校验证据</div><div>完成后将展示结果来源与引用</div></div>${state.request.error?`<div class="request-error">${escapeHtml(state.request.error)}</div><button class="retry" onclick="${state.request.operation==='compare'?'runComparison()':'startAnalysis()'}">重新尝试</button>`:''}</div></section>`;

screens.report=()=>{
  const report=state.report;
  if(!report)return protectedEmpty('还没有生成分析报告','needs');
  const advantages=safeArray(report.advantages);
  const risks=safeArray(report.risks);
  const unknowns=safeArray(report.unknowns);
  const bullets=[...advantages.map(text=>`<div class="bullet"><span class="ico good">✓</span><span>${escapeHtml(text)}</span></div>`),...risks.map(text=>`<div class="bullet"><span class="ico bad">!</span><span>${escapeHtml(text)}</span></div>`),...unknowns.map(text=>`<div class="bullet"><span class="ico warn">?</span><span>${escapeHtml(text)}</span></div>`)].join('');
  const rows=safeArray(report.aspects).map(item=>`<button class="metric-row action evidence-button" onclick="openEvidence('${item.aspect}')"><div class="metric-top"><b>${escapeHtml(aspectLabels[item.aspect]||item.aspect)}</b><span class="badge ${item.evidence_strength==='insufficient'?'low':item.evidence_strength==='weak'?'mid':''}">${escapeHtml(strengthLabels[item.evidence_strength]||item.evidence_strength)}</span></div><div class="evidence-counts"><span class="pos">支持 ${item.support_count}</span><span class="neg">反对 ${item.oppose_count}</span><span>混合 ${item.mixed_count||0}</span></div><p>${escapeHtml(item.summary)}</p></button>`).join('');
  return `${navTop('confirm')}<section class="report-head"><div class="tiny">${escapeHtml(report.product.display_name)} · 需求版本 1</div><h1>总体判断：${escapeHtml(verdictLabels[report.verdict]||report.verdict)}</h1><div class="match"><strong>${escapeHtml(sceneLabel())}</strong><span>${escapeHtml(strengthLabels[report.evidence_strength]||report.evidence_strength)}</span></div><div class="disclaimer">适配判断表示证据方向；证据强度表示结论可靠程度。两者都不是购买成功概率。</div></section><div class="summary-card">${resultModeBanner(report.meta)}<h3>一句话判断</h3><p class="sub">${escapeHtml(report.summary)}</p>${bullets||'<p class="sub">暂无更多结论。</p>'}</div><section class="metric">${rows}<article class="metric-row action" onclick="go('compareSelect')"><div class="metric-top"><b>与另一款匿名样本比较</b><button class="link">选择商品 ›</button></div><p>比较会沿用同一版需求，不把无数据解释为表现差。</p></article><button class="text-link" onclick="go('states')">查看异常与降级原则 ›</button></section>`;
};

screens.evidence=()=>{
  const items=state.evidenceFilter==='all'?state.evidence:state.evidence.filter(item=>item.stance===state.evidenceFilter);
  const tabs=['all','support','oppose','mixed'].map(key=>`<button class="chip ${state.evidenceFilter===key?'active':''}" aria-pressed="${state.evidenceFilter===key}" onclick="setEvidenceFilter('${key}')">${key==='all'?'全部':stanceLabels[key]} ${key==='all'?state.evidence.length:state.evidence.filter(item=>item.stance===key).length}</button>`).join('');
  const cards=items.map(item=>`<article class="evidence"><div class="evidence-head"><span>${escapeHtml(stanceLabels[item.stance]||item.stance)}</span><span>${escapeHtml(item.id)}</span></div><blockquote>“${escapeHtml(item.quote)}”</blockquote><div class="translation">AI中文摘要：${escapeHtml(item.summary_zh)}</div><p class="source-note">评分：${item.rating??'未提供'} · 验证购买：${item.verified_purchase===true?'是':item.verified_purchase===false?'否':'未提供'} · 有用票：${item.helpful_votes??'未提供'}</p><span class="source-chip">${item.source_kind==='demo_cache'?'演示缓存':'派生数据'} · ${escapeHtml(item.source_ref||'未提供来源键')}</span></article>`).join('');
  return `${navTop('report')}<section class="content"><div class="eyebrow">${escapeHtml(aspectLabels[state.selectedAspect]||state.selectedAspect)} · 证据详情</div><h1 class="section-title">结论来自哪些片段</h1><p class="section-copy">英文短片段是依据，中文内容仅为摘要。片段数不等于独立用户数。</p>${resultModeBanner(state.report&&state.report.meta)}<div class="evidence-tabs">${tabs}</div>${cards||'<div class="empty-state">当前筛选条件下没有证据。</div>'}</section>`;
};

screens.compareSelect=()=>`${navTop('report')}<section class="content"><div class="eyebrow">03 选择对比商品</div><h1 class="section-title">沿用同一需求比较</h1><p class="section-copy">当前需求：${escapeHtml(needSummary())}。MVP固定比较两款匿名样本。</p><button class="product-choice ${state.compareProduct==='demo-tws-b'?'selected':''}" onclick="selectCompareProduct('demo-tws-b')"><span class="product-icon">B</span><span><h3>样本耳机 B</h3><p>系统会以与样本A完全相同的需求、阈值和证据规则生成报告。</p></span></button><div class="missing">两款商品的证据量可能不同。系统允许返回“无明确胜者”。</div>${state.request.error?`<div class="request-error">${escapeHtml(state.request.error)}</div>`:''}</section><button class="cta" ${state.compareProduct?'':'disabled'} onclick="runComparison()">生成比较结果</button>`;

screens.compare=()=>{
  const comparison=state.comparison;
  if(!comparison)return protectedEmpty('还没有生成比较结果','compareSelect');
  const products=Object.fromEntries(comparison.products.map(item=>[item.product.id,item]));
  const rows=safeArray(comparison.aspect_rows).map(row=>`<div class="compare-row"><div>${escapeHtml(aspectLabels[row.aspect]||row.aspect)}</div>${productIds.map(id=>{const item=row.products[id];return `<div><span class="compare-cell-title">${escapeHtml(item?verdictLabels[item.verdict]:'无数据')}</span><br>${item?`${item.support_count}支持 / ${item.oppose_count}反对`:'—'}</div>`}).join('')}</div>`).join('');
  const winner=comparison.winner_product_id?(products[comparison.winner_product_id]?.product.display_name||comparison.winner_product_id):'无明确胜者';
  return `${navTop('report')}<section class="content"><div class="eyebrow">同一需求下的比较</div><h1 class="section-title">${escapeHtml(winner)}</h1><p class="section-copy">比较需求：${escapeHtml(needSummary())}</p>${resultModeBanner(comparison.meta)}<div class="no-winner"><b>比较结论：</b>${escapeHtml(comparison.conclusion)}</div><div class="compare-table"><div class="compare-row"><div>维度</div><div>样本A</div><div>样本B</div></div>${rows}</div><p class="source-note">比较不提供购买按钮或强制推荐；证据不足时保留“无明确胜者”。</p></section>`;
};

screens.states=()=>`${navTop('report')}<section class="content"><div class="eyebrow">异常与降级状态</div><h1 class="section-title">系统不能可靠回答时怎么办</h1><p class="section-copy">选择一个状态，查看面向用户的解释和恢复动作。</p><div class="chips">${['insufficient','conflict','timeout','unavailable'].map(key=>`<button class="chip ${state.demoState===key?'active':''}" onclick="setDemoState('${key}')">${{insufficient:'证据不足',conflict:'观点冲突',timeout:'分析超时',unavailable:'商品不可分析'}[key]}</button>`).join('')}</div>${statePreview()}</section>`;

screens.baseline=()=>`${navTop('product')}<div class="timer"><span id="timerText">基线任务计时未开始</span><button onclick="toggleTimer()" id="timerButton">开始计时</button></div><section class="content"><div class="eyebrow">用户测试 基线材料</div><h1 class="section-title">直接浏览普通评论</h1><p class="section-copy">任务：判断这款匿名样本是否适合每天地铁通勤和办公室视频会议。</p>${[['★★★★★','Bass is decent and the price is fair.'],['★★★☆☆','It connects to my phone, but I did not test calls.'],['★★☆☆☆','Guitars often sound inaccurate and details are weak.'],['★★★★☆','Comfortable for casual listening, no comment on subway noise.']].map(([stars,text])=>`<article class="baseline-review"><span class="stars">${stars}</span><p>${text}</p></article>`).join('')}<div class="missing">这些内容是固定测试材料，不属于实时AI分析。完成判断后记录用时和结论。</div></section>`;

function protectedEmpty(message,back){return `${navTop(back)}<section class="content"><div class="empty-state">${escapeHtml(message)}<br><button class="retry" onclick="go('${back}')">返回继续</button></div></section>`}

function localNeed(){
  const text=state.freeText.trim();
  const scenes=new Set(state.scenes);
  const aspects=new Set(state.aspects);
  const constraints=[];
  if(/地铁|公交|通勤|路上/.test(text)){scenes.add('commute');aspects.add('noise_cancellation')}
  if(/会议|开会|通话|麦克风/.test(text)){scenes.add('meeting');aspects.add('call_quality')}
  if(/跑步|健身|运动/.test(text)){scenes.add('exercise');aspects.add('comfort')}
  if(/久戴|长时间|一整天/.test(text)){scenes.add('long_wear');aspects.add('comfort')}
  if(/断连|连接不稳|掉线/.test(text)){aspects.add('connection');constraints.push({code:'no_frequent_disconnect',label:'不能频繁断连',hard:true})}
  if(/续航|电量|充电/.test(text))aspects.add('battery');
  if(/音质|低音|声音|音乐/.test(text))aspects.add('sound_quality');
  if(/降噪|安静|噪音/.test(text))aspects.add('noise_cancellation');
  if(!scenes.size)scenes.add('general');
  if(!aspects.size)aspects.add('connection');
  return {raw_text:text,scenes:[...scenes],aspects:[...aspects].map(name=>({name,priority:state.aspects.has(name)?3:2})),constraints};
}

function tagList(group,values){
  if(!values.length)return '<span class="sub">未识别</span>';
  const need=currentNeed();
  return values.map(value=>{
    const label=group==='scenes'?(sceneLabels[value]||value):group==='aspects'?(aspectLabels[value]||value):(need.constraints.find(item=>item.code===value)?.label||value);
    return `<span class="tag">${escapeHtml(label)}<button aria-label="删除${escapeHtml(label)}" onclick="removeTag('${group}','${value}')">×</button></span>`;
  }).join('');
}

function toggleSelection(group,value){state[group].has(value)?state[group].delete(value):state[group].add(value);state.parsedNeed=null;state.request.error='';render('needs')}

async function prepareConfirmation(){
  if(!state.scenes.size&&!state.aspects.size&&!state.freeText.trim()){state.request.error='请至少选择一个场景、关注维度或填写一句需求。';render('needs');return}
  state.request={busy:true,operation:'parse',error:''};render('needs');
  try{
    const response=await tingjianApi.parseNeed({text:state.freeText.trim(),selected_scenes:[...state.scenes],selected_aspects:[...state.aspects]});
    state.parsedNeed=response.need;state.parseMode=response.mode;
  }catch(error){
    state.parsedNeed=localNeed();state.parseMode='frontend_cache';state.request.error=`后端暂不可用，已使用本地规则供你确认：${error.message}`;
  }
  state.request.busy=false;go('confirm');
}

function removeTag(group,value){
  const need=currentNeed();
  if(group==='scenes'){need.scenes=need.scenes.filter(item=>item!==value);if(!need.scenes.length)need.scenes=['general'];state.scenes.delete(value)}
  if(group==='aspects'){need.aspects=need.aspects.filter(item=>item.name!==value);state.aspects.delete(value)}
  if(group==='constraints')need.constraints=need.constraints.filter(item=>item.code!==value);
  state.parsedNeed=need;render('confirm');
}

async function startAnalysis(){
  state.request={busy:true,operation:'report',error:''};go('loading');
  try{state.report=await tingjianApi.createReport({product_id:'demo-tws-a',need:currentNeed()})}
  catch(error){state.report=fallbackReport('demo-tws-a',currentNeed());state.request.error=`后端暂不可用，已切换到明确标注的前端缓存：${error.message}`}
  state.request.busy=false;go('report');
}

async function openEvidence(aspect){
  state.selectedAspect=aspect;state.evidenceFilter='all';
  try{const response=await tingjianApi.getEvidence('demo-tws-a',{aspect,limit:30});state.evidence=response.items}
  catch{state.evidence=safeArray(state.report&&state.report.evidence_preview).filter(item=>item.aspect===aspect)}
  go('evidence');
}

function setEvidenceFilter(filter){state.evidenceFilter=filter;render('evidence')}
function selectCompareProduct(productId){state.compareProduct=productId;state.request.error='';render('compareSelect')}

async function runComparison(){
  if(!state.compareProduct)return;
  state.request={busy:true,operation:'compare',error:''};go('loading');
  try{state.comparison=await tingjianApi.compare({product_ids:['demo-tws-a',state.compareProduct],need:currentNeed()})}
  catch(error){state.comparison=fallbackComparison(currentNeed());state.request.error=`后端暂不可用，比较页使用演示缓存：${error.message}`}
  state.request.busy=false;go('compare');
}

function fallbackEvidence(productId){
  const suffix=productId.endsWith('a')?'a':'b';
  const data=suffix==='a'?
    [
      ['sound_quality','support','Bass sounds full and enjoyable for podcasts and pop music.','低频饱满，适合播客和流行音乐。',4],
      ['sound_quality','oppose','Instrument separation becomes muddy in busy tracks.','复杂曲目中的乐器分离度不足。',2],
      ['connection','support','Pairing was quick and the connection stayed stable at my desk.','桌面使用时配对快速且连接稳定。',5],
      ['connection','oppose','The left earbud disconnected twice during my walk.','步行时左耳出现过两次断连。',2],
      ['call_quality','mixed','Calls are clear indoors, but street noise reaches the microphone.','室内通话清楚，但街道噪声会进入麦克风。',3],
      ['battery','support','The battery lasted through a full workday with short breaks.','间歇使用时续航可覆盖一个工作日。',4],
      ['comfort','mixed','Comfortable for two hours, then my ears felt some pressure.','两小时内舒适，之后出现压迫感。',3],
      ['noise_cancellation','oppose','Train rumble is reduced, but announcements remain easy to hear.','能削弱列车低频，但广播仍较清楚。',3],
    ]:
    [
      ['noise_cancellation','support','It cuts most of the low train noise on my commute.','通勤时能削弱大部分列车低频噪声。',5],
      ['noise_cancellation','oppose','Wind noise is noticeable when transparency mode is on.','开启通透模式后风噪明显。',2],
      ['comfort','support','The small tips stay comfortable through long meetings.','小号耳塞在长会议中仍较舒适。',5],
      ['connection','mixed','Stable with my phone, but switching to a laptop takes time.','连接手机稳定，但切换电脑较慢。',3],
      ['call_quality','mixed','Voices are understandable in a quiet room, not on a busy road.','安静室内语音可懂，嘈杂道路表现不足。',3],
      ['battery','support','One charge covered several commuting sessions.','一次充电可覆盖多次通勤。',4],
      ['sound_quality','support','Vocals are forward and speech is easy to follow.','人声靠前，语音内容容易听清。',4],
      ['sound_quality','oppose','Treble can sound sharp at higher volume.','大音量下高频可能偏尖锐。',2],
    ];
  return data.map((row,index)=>({id:`ev-${suffix}-${String(index+1).padStart(3,'0')}`,product_id:productId,aspect:row[0],stance:row[1],quote:row[2],summary_zh:row[3],rating:row[4],helpful_votes:index%3,verified_purchase:index%2===0,source_kind:'demo_cache',source_ref:`demo-cache/${suffix}-${index+1}`}));
}

function fallbackReport(productId,need){
  const evidence=fallbackEvidence(productId);
  const presets=productId.endsWith('a')?{
    noise_cancellation:[1,2,'insufficient'],call_quality:[2,1,'weak'],connection:[5,2,'medium'],comfort:[2,2,'weak'],battery:[6,2,'medium'],sound_quality:[7,3,'medium']
  }:{
    noise_cancellation:[6,2,'medium'],call_quality:[2,2,'weak'],connection:[3,2,'weak'],comfort:[8,2,'medium'],battery:[3,2,'weak'],sound_quality:[5,4,'medium']
  };
  const requested=new Set(need.aspects.map(item=>item.name));
  const aspects=aspectOptions.map(({code})=>{
    const [support,oppose,strength]=presets[code];
    const verdict=strength==='insufficient'?'uncertain':support>oppose*1.8?'good_fit':oppose>support?'poor_fit':'uncertain';
    return {aspect:code,verdict,evidence_strength:strength,support_count:support,oppose_count:oppose,mixed_count:code==='call_quality'||code==='comfort'?1:0,summary:`演示缓存中，${aspectLabels[code]}有${support}条支持、${oppose}条反对证据。`,evidence_ids:evidence.filter(item=>item.aspect===code).map(item=>item.id)};
  });
  const core=aspects.filter(item=>requested.has(item.aspect));
  const hasInsufficient=core.some(item=>item.evidence_strength==='insufficient');
  const verdict=hasInsufficient?'uncertain':core.length&&core.every(item=>item.verdict==='good_fit')?'good_fit':'uncertain';
  return {report_id:`report-${productId.endsWith('a')?'aaaaaaaaaaaaaaaa':'bbbbbbbbbbbbbbbb'}`,product:{id:productId,display_name:productId.endsWith('a')?'样本耳机 A':'样本耳机 B',description:'用于验证产品交互的匿名演示样本',source_kind:'demo_cache'},need,verdict,evidence_strength:hasInsufficient?'weak':'medium',summary:'当前结果来自前端演示缓存，只用于展示检索、聚合和引用交互。连接真实后端后将根据实际证据重新生成。',advantages:['部分关注维度存在直接支持片段。'],risks:['正反观点同时存在，不能只依据总体评分。'],unknowns:hasInsufficient?['至少一个核心维度证据不足。']:[],aspects,citation_ids:evidence.map(item=>item.id),evidence_preview:evidence,warnings:['frontend offline fallback'],meta:{mode:'frontend_cache',model:null,generated_at:new Date().toISOString(),is_demo_cache:true,disclaimer:'演示缓存，不代表真实商品评价或购买建议。'}};
}

function fallbackComparison(need){
  const reports=productIds.map(id=>fallbackReport(id,need));
  return {comparison_id:'compare-cccccccccccccccc',need,winner_product_id:null,conclusion:'两款样本在核心场景中都存在证据不足或观点冲突，因此演示缓存不指定胜者。',products:reports.map(report=>({product:report.product,verdict:report.verdict,evidence_strength:report.evidence_strength,summary:report.summary,report_id:report.report_id})),aspect_rows:aspectOptions.map(({code})=>({aspect:code,products:Object.fromEntries(reports.map(report=>[report.product.id,report.aspects.find(item=>item.aspect===code)]))})),warnings:['frontend offline fallback'],meta:{mode:'frontend_cache',model:null,generated_at:new Date().toISOString(),is_demo_cache:true,disclaimer:'演示缓存，不代表真实商品比较。'}};
}

function setDemoState(key){state.demoState=key;render('states')}
function statePreview(){const data={insufficient:['△','证据不足','当前没有足够的直接评论片段，无法判断该需求。','修改需求'],conflict:['⇄','观点冲突','支持和反对片段同时存在。系统保留分歧，不用证据强度掩盖冲突。','查看报告'],timeout:['…','分析超时','输入已保留。你可以重试，或查看明确标注的缓存结果。','重新分析'],unavailable:['○','暂不可分析','当前商品没有可映射的评论数据。普通评论入口仍然可用。','返回商品页']}[state.demoState];return `<article class="state-preview"><div class="symbol">${data[0]}</div><h2>${data[1]}</h2><p>${data[2]}</p><button class="retry" onclick="${state.demoState==='unavailable'?"go('product')":"go('needs')"}">${data[3]}</button></article>`}

let timerStart=null,timerHandle=null;
function toggleTimer(){const button=document.getElementById('timerButton');if(!timerStart){timerStart=Date.now();button.textContent='完成判断';timerHandle=setInterval(updateTimer,250)}else{clearInterval(timerHandle);updateTimer(true);button.disabled=true;button.textContent='已记录'}}
function updateTimer(done=false){const seconds=((Date.now()-timerStart)/1000).toFixed(1);document.getElementById('timerText').textContent=`${done?'基线任务完成':'正在计时'} ${seconds} 秒`}

function go(name){history.pushState({},'',`?screen=${encodeURIComponent(name)}`);render(name)}
function render(name){const target=screens[name]?name:'product';document.getElementById('app').innerHTML=screens[target]();document.getElementById('app').scrollTop=0}
window.onpopstate=()=>render(new URLSearchParams(location.search).get('screen')||'product');

async function refreshHealth(){
  try{state.health=await tingjianApi.health()}
  catch(error){state.health={status:'offline',mode:'frontend_cache',model_configured:false,is_demo_cache:true,evidence_source:'demo_cache',evidence_loaded:0,error:error.message}}
  if((new URLSearchParams(location.search).get('screen')||'product')==='product')render('product');
}

render(new URLSearchParams(location.search).get('screen')||'product');
refreshHealth();
