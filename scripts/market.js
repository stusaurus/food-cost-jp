(()=>{
document.querySelectorAll('img[data-image-fallback]').forEach(img=>{const fallback=()=>{const url=img.dataset.imageFallback;if(url){delete img.dataset.imageFallback;img.src=url}};img.addEventListener('error',fallback,{once:true});if(img.complete&&!img.naturalWidth)fallback()});
const op=window.foodCostOperatorTest===true;
const send=(n,x={})=>{if(typeof gtag==='function')gtag('event',n,{site_id:'food_cost_jp',...(op?{operator_test:'1'}:{}),...x})};
window.foodCostTrack=send;
document.addEventListener('click',e=>{
  const a=e.target.closest('a[data-affiliate]');if(!a)return;
  const pos=a.dataset.position||'comparison_table';
  const x={affiliate:'rakuten',conversion_source:pos,category_id:a.dataset.category,product_id:a.dataset.productId,product_name:a.dataset.productName,rank:a.dataset.rank,comparison_metric:a.dataset.metric,unit_price:Number(a.dataset.unitPrice||0),shipping_status:a.dataset.shipping,click_position:pos,cta_variant:a.dataset.ctaVariant||'standard',cta_text:(a.textContent||'').trim(),page_path:location.pathname,link_url:a.href};
  send('product_result_click',x);send('affiliate_click',x)
});
document.querySelectorAll('[data-start-route]').forEach(a=>a.addEventListener('click',()=>send('home_start_route',{route:a.dataset.startRoute||''})));
document.querySelectorAll('[data-product-extra]').forEach(d=>d.addEventListener('toggle',()=>{if(d.open)send('product_detail_open',{page_path:location.pathname})}));
document.querySelectorAll('[data-sort]').forEach(s=>s.addEventListener('change',()=>{
  const root=s.closest('[data-comparison]'),body=root.querySelector('tbody'),rows=[...body.querySelectorAll('tr')],m=s.value;
  rows.sort((a,b)=>Number(a.dataset[m]||Infinity)-Number(b.dataset[m]||Infinity));
  const base=Number(root.dataset.startRank||1);
  rows.forEach((r,i)=>{
    const n=base+i,rankCell=r.querySelector('[data-rank]'),rankSpan=rankCell?.querySelector('.rank');
    if(rankSpan){rankSpan.textContent=n;rankSpan.classList.toggle('top',n<=3)}
    const link=r.querySelector('a[data-affiliate]');if(link)link.dataset.rank=String(n);
    body.appendChild(r)
  });
  send('comparison_sort',{category_id:s.dataset.category,comparison_metric:m})
}));
const applyFilters=root=>{
  const size=root.querySelector('[data-filter]')?.value||'all';
  const term=(root.querySelector('[data-search]')?.value||'').trim().toLowerCase();
  let shown=0;
  root.querySelectorAll('tbody tr').forEach(r=>{
    const sizeOk=size==='all'||(root.dataset.shoppingIntent?r.dataset.shoppingBucket:r.dataset.bucket)===size;
    const textOk=!term||(r.dataset.searchText||'').includes(term);
    r.hidden=!(sizeOk&&textOk);
    if(!r.hidden)shown++;
  });
  const empty=root.querySelector('[data-empty-filter]');
  if(empty)empty.style.display=shown?'none':'block';
};
document.querySelectorAll('[data-filter]').forEach(s=>s.addEventListener('change',()=>{
  const root=s.closest('[data-comparison]');applyFilters(root);
  send('comparison_filter_use',{category_id:s.dataset.category,filter_value:s.value})
}));
document.querySelectorAll('[data-search]').forEach(input=>input.addEventListener('change',()=>{
  const root=input.closest('[data-comparison]');applyFilters(root);
  send('comparison_search_use',{category_id:input.dataset.category,search_term:input.value.trim()})
}));
const shelfSeen=new WeakSet();
const shelfView=el=>{if(!el||shelfSeen.has(el)||el.closest('[hidden]'))return;shelfSeen.add(el);send('market_shelf_view',{shelf_id:el.dataset.marketShelf,product_count:el.querySelectorAll('[data-affiliate]').length,category_id:[...new Set([...el.querySelectorAll('[data-affiliate]')].map(a=>a.dataset.category))].length===1?el.querySelector('[data-affiliate]')?.dataset.category:'all',category_ids:[...new Set([...el.querySelectorAll('[data-affiliate]')].map(a=>a.dataset.category))].join(',')})};
if(!('IntersectionObserver' in window))document.querySelectorAll('[data-market-shelf]').forEach(shelfView);
if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting)shelfView(entry.target)}),{threshold:.1});document.querySelectorAll('[data-market-shelf]').forEach(el=>observer.observe(el))}
document.addEventListener('click',e=>{const a=e.target.closest('a[data-affiliate]');const shelf=a?.closest('[data-market-shelf]');if(shelf)send('market_shelf_product_click',{shelf_id:shelf.dataset.marketShelf,category_id:a.dataset.category,product_id:a.dataset.productId,cta_variant:a.dataset.ctaVariant})});
const finder=document.querySelector('[data-finder]');
if(finder){
  let category='all',purpose='',intent='',route='';
  const routeStage=finder.querySelector('[data-finder-route-stage]');
  const categoryStage=finder.querySelector('[data-finder-category-stage]'),purposeStage=finder.querySelector('[data-finder-purpose-stage]'),resultStage=finder.querySelector('[data-finder-result-stage]'),status=finder.querySelector('[data-finder-status]');
  const show=el=>{el.hidden=false;const first=el.querySelector('summary,button');first?.focus({preventScroll:true});const top=el.getBoundingClientRect().top;if(top<0||top>window.innerHeight*.65)el.scrollIntoView?.({block:'start',behavior:window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches?'instant':'smooth'})};
  const hide=el=>el.hidden=true;
  const results=()=>{
    hide(routeStage);hide(purposeStage);hide(categoryStage);show(resultStage);
    let current;
    finder.querySelectorAll('[data-finder-picks]').forEach(panel=>{panel.hidden=panel.dataset.finderPicks!==category+':'+purpose;if(!panel.hidden)current=panel});
    const count=current?.querySelectorAll('[data-affiliate]').length||0;
    const tailored=Boolean(current?.querySelector('[data-recommendation-shelf]'));
    status.textContent=count?(tailored?'条件に合わせて、役割の違う'+count+'候補に絞りました。単価だけでなく総額も比べて選べます。':'それなら、この棚から。 '+count+'件の候補があります。'):'この条件の候補は現在ありません。別の買い方も見てみましょう。';
    send('finder_complete',{category_id:category,shopping_intent:intent,product_count:count});
    send('quick_finder_complete',{category_id:category,finder_purpose:purpose});
    if(!('IntersectionObserver' in window))shelfView(current?.querySelector('[data-market-shelf]'));
  };
  const reset=()=>{purpose='';category='all';route='';show(routeStage);hide(purposeStage);hide(categoryStage);hide(resultStage);status.textContent='';finder.querySelectorAll('[data-finder-picks]').forEach(x=>x.hidden=true);finder.querySelectorAll('[aria-pressed]').forEach(x=>x.setAttribute('aria-pressed','false'));finder.querySelectorAll('.selected').forEach(x=>x.classList.remove('selected'));finder.querySelectorAll('.finder-aisle').forEach(x=>x.open=false)};
  const selectRoute=(key,source='entry')=>{
    route=key;category='all';status.textContent='';hide(routeStage);hide(purposeStage);hide(categoryStage);hide(resultStage);
    finder.querySelectorAll('[data-entry-route]').forEach(x=>{x.classList.toggle('selected',x.dataset.entryRoute===key);x.setAttribute('aria-pressed',String(x.dataset.entryRoute===key))});
    send('entry_route_select',{entry_route:key,entry_source:source});
    if(key==='advisor'){show(purposeStage);return}
    intent=key==='deal'?'cheap':'known';purpose='cheap';send('shopping_intent_select',{shopping_intent:intent});
    if(key==='known'){show(categoryStage);status.textContent='いつもの食品を、売り場から選びましょう。'}else results();
  };
  finder.querySelectorAll('[data-entry-route]').forEach(btn=>btn.addEventListener('click',()=>selectRoute(btn.dataset.entryRoute)));
  document.querySelector('[data-hero-known]')?.addEventListener('click',()=>selectRoute('known'));
  document.querySelector('[data-hero-primary]')?.addEventListener('click',()=>{reset();selectRoute('advisor','hero');send('hero_primary_cta',{destination:'shopping-intent',entry_route:'advisor'})});
  finder.querySelectorAll('[data-finder-purpose]').forEach(btn=>btn.addEventListener('click',()=>{
    purpose=btn.dataset.finderPurpose;intent=purpose;category='all';
    finder.querySelectorAll('[data-finder-purpose]').forEach(x=>{x.classList.toggle('selected',x===btn);x.setAttribute('aria-pressed',String(x===btn))});
    send('shopping_intent_select',{shopping_intent:intent});results();
  }));
  finder.querySelectorAll('[data-finder-category]').forEach(btn=>btn.addEventListener('click',()=>{category=btn.dataset.finderCategory;finder.querySelectorAll('[data-finder-category]').forEach(x=>{x.classList.toggle('selected',x===btn);x.setAttribute('aria-pressed',String(x===btn))});send('quick_finder_category',{category_id:category});send('category_select_after_intent',{category_id:category,shopping_intent:intent});results()}));
  finder.querySelector('[data-finder-narrow]')?.addEventListener('click',()=>{hide(resultStage);show(categoryStage);status.textContent='この買い方のまま、売り場を選べます。'});
  finder.querySelectorAll('[data-finder-back]').forEach(btn=>btn.addEventListener('click',reset));
  finder.querySelector('[data-finder-reset]')?.addEventListener('click',reset);
}
const pick=new URLSearchParams(location.search).get('pick');
if(pick&&document.querySelector('[data-comparison]')){
  const root=document.querySelector('[data-comparison]');
  const filter=root.querySelector('[data-filter]');
  const sort=root.querySelector('[data-sort]');
  if(filter&&(pick==='small'||pick==='large'||pick==='storage')){root.dataset.shoppingIntent=pick;filter.value=pick==='storage'?'small':pick;if(['carbonated-water','mineral-water'].includes(filter.dataset.category)){filter.querySelector('[value=small]').textContent='合計12L以下';filter.querySelector('[value=large]').textContent='合計12L超'}const label=root.querySelector('[data-intent-note]');if(label)label.textContent='買い方で絞った一覧：少量側 / 大容量側は合計量を基準にしています。'}
  if(filter&&pick==='storage')filter.value='small';
  if(sort&&(pick==='budget'||pick==='storage')){sort.value='price';sort.dispatchEvent(new Event('change'))}
  const details=root.closest('details');if(details)details.open=true;
  applyFilters(root);
  send('quick_finder_landing',{category_id:filter?.dataset.category||'',finder_purpose:pick})
}

document.addEventListener('click',e=>{
  const rangeBtn=e.target.closest('[data-history-range]');
  if(!rangeBtn)return;
  const card=rangeBtn.closest('[data-history-card]');if(!card)return;
  const range=rangeBtn.dataset.historyRange;
  card.querySelectorAll('[data-history-range]').forEach(btn=>btn.classList.toggle('selected',btn===rangeBtn));
  card.querySelectorAll('[data-history-panel]').forEach(panel=>panel.hidden=panel.dataset.historyPanel!==range);
  send('price_history_range_change',{range_value:range,page_path:location.pathname})
});
const SAVED_KEY='food_cost_saved_v1',COMPARE_KEY='food_cost_compare_v1';
const readList=key=>{try{const v=JSON.parse(localStorage.getItem(key)||'[]');return Array.isArray(v)?v:[]}catch(e){return[]}};
const writeList=(key,value)=>{try{localStorage.setItem(key,JSON.stringify(value))}catch(e){}};
const itemKey=x=>x.category+'|'+x.id;
const fromButton=btn=>({
  id:btn.dataset.productId||'',
  name:btn.dataset.productName||'',
  category:btn.dataset.productCategory||'',
  categoryName:btn.dataset.productCategoryName||'',
  price:Number(btn.dataset.productPrice||0),
  unit:Number(btn.dataset.productUnit||0),
  unitLabel:btn.dataset.productUnitLabel||'',
  metric:btn.dataset.productMetric||'',
  shipping:btn.dataset.productShipping||'',
  signal:btn.dataset.productSignal||'',
  signalTone:btn.dataset.productSignalTone||'neutral',
  verified:true,
  quantity:btn.dataset.productQuantity||'',
  url:btn.dataset.productUrl||'',
  image:btn.dataset.productImage||''
});
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const money=n=>'¥'+Number(n||0).toLocaleString('ja-JP',{maximumFractionDigits:1});
const validEntry=x=>x&&typeof x.id==='string'&&typeof x.category==='string';
let saved=readList(SAVED_KEY).filter(validEntry).slice(0,30),compared=readList(COMPARE_KEY).filter(validEntry).slice(0,3);
compared=compared.filter(x=>x.category===compared[0]?.category);
const current=new Map([...document.querySelectorAll('[data-save-product]')].map(btn=>{const x=fromButton(btn);return[itemKey(x),x]}));
const refreshVisible=x=>current.get(itemKey(x))||{...x,verified:false};
saved=saved.map(refreshVisible);compared=compared.map(refreshVisible);
const retailLink=(x,source,rank)=>{
  let safe=false;try{const u=new URL(x.url);safe=u.protocol==='https:'&&u.hostname==='hb.afl.rakuten.co.jp'}catch(e){}
  if(!x.verified||!safe)return '<span class="fine">最新の掲載を確認できません。売り場から選び直してください。</span>';
  return '<a href="'+esc(x.url)+'" target="_blank" rel="nofollow sponsored noopener" data-affiliate="rakuten" data-position="'+source+'" data-category="'+esc(x.category)+'" data-product-id="'+esc(x.id)+'" data-product-name="'+esc(x.name)+'" data-rank="'+rank+'" data-metric="'+esc(x.metric)+'" data-unit-price="'+x.unit+'" data-shipping="'+esc(x.shipping)+'">楽天で確認 →</a>';
};
const toastEl=document.querySelector('[data-toast]');
let toastTimer;
const toast=message=>{
  if(!toastEl)return;
  toastEl.textContent=message;toastEl.hidden=false;
  clearTimeout(toastTimer);toastTimer=setTimeout(()=>toastEl.hidden=true,1800)
};
const syncUtilityButtons=()=>{
  const savedKeys=new Set(saved.map(itemKey)),compareKeys=new Set(compared.map(itemKey));
  document.querySelectorAll('[data-save-product]').forEach(btn=>{
    const active=savedKeys.has((btn.dataset.productCategory||'')+'|'+(btn.dataset.productId||''));
    btn.classList.toggle('active',active);btn.setAttribute('aria-pressed',String(active));btn.textContent=active?'✓ メモ済み':'＋ 買い物メモ'
  });
  document.querySelectorAll('[data-compare-product]').forEach(btn=>{
    const active=compareKeys.has((btn.dataset.productCategory||'')+'|'+(btn.dataset.productId||''));
    btn.classList.toggle('active',active);btn.setAttribute('aria-pressed',String(active));btn.textContent=active?'✓ 比較中':'＋ 比較する'
  });
  const count=document.querySelector('[data-saved-count]');if(count)count.textContent=String(saved.length)
};
const renderSaved=()=>{
  const root=document.querySelector('[data-saved-list]');if(!root)return;
  if(!saved.length){root.innerHTML='<div class="utility-empty">保存した商品はまだありません。商品カードの「買い物メモ」から残せます。</div>';return}
  const compareKeys=new Set(compared.map(itemKey));
  root.innerHTML=saved.map((x,i)=>{
    const key=itemKey(x),tone=['buy','wait','neutral'].includes(x.signalTone)?x.signalTone:'neutral';
    const signal=x.signal?'<span class="saved-signal '+tone+'">'+esc(x.signal)+'</span>':'';
    const compareLabel=compareKeys.has(key)?'✓ 比較中':'＋ 比較に追加';
    return '<div class="saved-item">'+
      (x.image?'<img src="'+esc(x.image)+'" alt="">':'<div></div>')+
      '<div class="saved-item-main"><div class="saved-item-head">'+signal+'<strong>'+esc(x.name)+'</strong></div><small>'+esc(x.categoryName)+' ・ '+(x.verified?'掲載価格 ':'保存時価格 ')+money(x.unit)+' '+esc(x.unitLabel)+' ・ '+money(x.price)+' ・ '+esc(x.shipping==='included'?'送料込み':'送料別・不明')+'</small><div class="saved-item-actions"><button type="button" class="saved-compare" data-compare-saved="'+esc(key)+'">'+compareLabel+'</button>'+retailLink(x,'saved_modal',i+1)+'</div></div>'+
      '<button type="button" class="saved-remove" data-remove-saved="'+esc(key)+'" aria-label="保存から削除">削除</button></div>'
  }).join('')
};
const renderCompare=()=>{
  const root=document.querySelector('[data-compare-table]');if(!root)return;
  if(!compared.length){root.innerHTML='<div class="utility-empty">「比較する」から同じ食品を最大3商品まで選べます。</div>';return}
  const cells=(label,fn)=>'<tr><th scope="row">'+esc(label)+'</th>'+compared.map((x,i)=>'<td>'+fn(x,i)+'</td>').join('')+'</tr>';
  const signalCell=x=>{
    const tone=['buy','wait','neutral'].includes(x.signalTone)?x.signalTone:'neutral';
    return x.signal?'<span class="compare-signal '+tone+'">'+esc(x.signal)+'</span>':'—'
  };
  root.innerHTML='<div class="compare-table"><table><thead><tr><th>比較項目</th>'+
    compared.map(x=>'<th>'+esc(x.name)+'</th>').join('')+
    '</tr></thead><tbody>'+
    cells('商品価格',x=>money(x.price))+
    cells('内容量',x=>esc(x.quantity))+
    cells('主要単価',x=>'<strong>'+money(x.unit)+'</strong><small class="compare-unit-label">'+esc(x.unitLabel)+'</small>')+
    cells('価格の状態',signalCell)+
    cells('送料',x=>x.shipping==='included'?'送料込み':'送料別・不明')+
    cells('データ',x=>x.verified?'現在の掲載価格':'保存時価格・要確認')+
    cells('販売先',(x,i)=>retailLink(x,'compare_modal',i+1))+
    '</tbody></table></div>'
};
const syncCompareBar=()=>{
  const bar=document.querySelector('[data-compare-bar]');if(!bar)return;
  bar.hidden=!compared.length;
  document.body.classList.toggle('has-compare',Boolean(compared.length));
  const summary=bar.querySelector('[data-compare-summary]');if(summary)summary.textContent=compared.length+'/3';
  const items=bar.querySelector('[data-compare-bar-items]');
  if(items)items.innerHTML=compared.map(x=>'<span class="compare-chip">'+(x.image?'<img src="'+esc(x.image)+'" alt="">':'')+'<span>'+esc(x.name)+'</span><button type="button" class="compare-remove" data-remove-compare="'+esc(itemKey(x))+'" aria-label="'+esc(x.name)+'を比較から外す">×</button></span>').join('');
  const open=bar.querySelector('[data-open-compare]');if(open)open.textContent=compared.length+'商品を比べる'
};
const persistUtilities=()=>{
  writeList(SAVED_KEY,saved);writeList(COMPARE_KEY,compared);
  syncUtilityButtons();syncCompareBar();renderSaved();renderCompare()
};
let activeModal=null,modalTrigger=null,modalScroll=0;
const focusable=modal=>Array.from(modal.querySelectorAll('button,a[href],input,select,summary,[tabindex="0"]')).filter(el=>!el.disabled&&el.getClientRects().length);
const closeModal=()=>{
  if(!activeModal)return;
  activeModal.hidden=true;activeModal=null;
  document.body.classList.remove('modal-open');document.body.style.top='';
  document.querySelectorAll('.market-masthead,header,nav,main,footer').forEach(el=>el.inert=false);
  window.scrollTo({top:modalScroll,behavior:'instant'});
  if(modalTrigger?.isConnected)modalTrigger.focus({preventScroll:true});
};
const openModal=modal=>{
  if(!modal)return;
  if(activeModal)closeModal();
  modalTrigger=document.activeElement;modalScroll=window.scrollY;activeModal=modal;
  document.body.style.top=-modalScroll+'px';document.body.classList.add('modal-open');
  // Some dialogs live inside main; keep their ancestor active and trap focus below.
  document.querySelectorAll('.market-masthead,header,nav,main,footer').forEach(el=>el.inert=!el.contains(modal));
  modal.hidden=false;focusable(modal)[0]?.focus({preventScroll:true});
};
document.addEventListener('click',e=>{
  const saveBtn=e.target.closest('[data-save-product]');
  if(saveBtn){
    const item=fromButton(saveBtn),key=itemKey(item),exists=saved.some(x=>itemKey(x)===key);
    saved=exists?saved.filter(x=>itemKey(x)!==key):[item,...saved].slice(0,30);
    persistUtilities();toast(exists?'保存から外しました':'買い物メモに保存しました。あとで価格と比較できます');
    send('product_save_toggle',{category_id:item.category,product_id:item.id,saved:exists?0:1});return
  }
  const compareSaved=e.target.closest('[data-compare-saved]');
  if(compareSaved){
    const item=saved.find(x=>itemKey(x)===compareSaved.dataset.compareSaved);
    if(!item)return;
    const key=itemKey(item),exists=compared.some(x=>itemKey(x)===key);
    if(exists){toast('この商品は比較中です');return}
    if(compared.length&&compared[0].category!==item.category){toast('比較は同じ食品カテゴリで選んでください');return}
    if(compared.length>=3){toast('比較できるのは3商品までです');return}
    compared.push(item);persistUtilities();toast('買い物メモから比較に追加しました');
    send('saved_to_compare',{category_id:item.category,product_id:item.id,compare_count:compared.length});return
  }
  const compareBtn=e.target.closest('[data-compare-product]');
  if(compareBtn){
    const item=fromButton(compareBtn),key=itemKey(item),exists=compared.some(x=>itemKey(x)===key);
    if(exists){compared=compared.filter(x=>itemKey(x)!==key);persistUtilities();toast('比較から外しました');return}
    if(compared.length&&compared[0].category!==item.category){toast('比較は同じ食品カテゴリで選んでください');return}
    if(compared.length>=3){toast('比較できるのは3商品までです');return}
    compared.push(item);persistUtilities();toast('比較に追加しました');
    send('product_compare_add',{category_id:item.category,product_id:item.id,compare_count:compared.length});return
  }
  const remove=e.target.closest('[data-remove-saved]');
  if(remove){saved=saved.filter(x=>itemKey(x)!==remove.dataset.removeSaved);persistUtilities();return}
  const removeCompare=e.target.closest('[data-remove-compare]');
  if(removeCompare){compared=compared.filter(x=>itemKey(x)!==removeCompare.dataset.removeCompare);persistUtilities();toast('比較から外しました');document.querySelector(compared.length?'[data-open-compare]':'[data-open-saved]')?.focus({preventScroll:true});return}
  if(e.target.closest('[data-open-saved]')){renderSaved();openModal(document.querySelector('[data-saved-modal]'));return}
  if(e.target.closest('[data-close-saved]')){closeModal();return}
  if(e.target.closest('[data-open-compare]')){renderCompare();openModal(document.querySelector('[data-compare-modal]'));send('product_compare_open',{compare_count:compared.length});return}
  if(e.target.closest('[data-close-compare]')){closeModal();return}
  if(e.target.closest('[data-clear-compare]')){compared=[];persistUtilities();toast('比較をクリアしました');return}
  const modal=e.target.closest('.utility-modal');
  if(modal&&e.target===modal)closeModal()
});
document.addEventListener('keydown',e=>{
  if(!activeModal)return;
  if(e.key==='Escape'){e.preventDefault();closeModal();return}
  if(e.key==='Tab'){
    const controls=focusable(activeModal),first=controls[0],last=controls[controls.length-1];
    if(!first)return;
    if(e.shiftKey&&(document.activeElement===first||!activeModal.contains(document.activeElement))){e.preventDefault();last.focus()}
    else if(!e.shiftKey&&(document.activeElement===last||!activeModal.contains(document.activeElement))){e.preventDefault();first.focus()}
  }
});
persistUtilities();
// Refresh old entries against the current validated snapshot; never show a
// missing listing's stored price as a current offer.
if((saved.length||compared.length)&&typeof fetch==='function')fetch('https://stusaurus.github.io/food-cost-jp/data/products.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('snapshot');return r.json()}).then(data=>{
 const live=new Map();Object.entries(data.categories||{}).forEach(([cat,payload])=>[...(payload.included||[]),...(payload.shipping_unknown||[])].forEach(item=>live.set(cat+'|'+item.id,item)));
 const refresh=x=>{const item=live.get(itemKey(x));if(!item)return {...x,verified:false};const metric=item.comparison_metric||x.metric||Object.keys(item.unit_prices)[0];return {...x,name:item.name,price:item.price,unit:item.unit_prices[metric],metric,unitLabel:item.unit_label||x.unitLabel,quantity:item.quantity_label||x.quantity,shipping:item.shipping_status,url:item.url,image:item.image,verified:true}};
 saved=saved.map(refresh);compared=compared.map(refresh);persistUtilities();
}).catch(()=>{});
})();
