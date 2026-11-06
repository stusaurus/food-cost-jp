/* No verified price or offer? Keep a usable quantity-only calculator.
 * This script cannot create seller, checkout, price, shipping or affiliate claims.
 */
(function(){
  'use strict';
  function countOnly(daily,days,stock){
    if(!Number.isSafeInteger(daily)||daily<1||daily>24
      ||!Number.isSafeInteger(days)||days<1||days>90
      ||!Number.isSafeInteger(stock)||stock<0||stock>100000)return null;
    const needed=daily*days;
    const shortage=Math.max(0,needed-stock);
    const boxes=Math.ceil(shortage/24);
    return {needed,shortage,boxes,leftover:stock+boxes*24-needed,noBuy:boxes===0};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={countOnly};
  if(typeof document==='undefined')return;
  const root=document.querySelector('[data-rice-quantity-only]');
  if(!root)return;
  const daily=root.querySelector('[data-rice-quantity-daily]');
  const days=root.querySelector('[data-rice-quantity-days]');
  const stock=root.querySelector('[data-rice-quantity-stock]');
  const result=root.querySelector('[data-rice-quantity-result]');
  const error=root.querySelector('[data-rice-quantity-error]');
  const form=root.querySelector('[data-rice-quantity-form]');
  const choices=[...root.querySelectorAll('[data-rice-quantity-choice]')];
  const fmt=n=>n.toLocaleString('ja-JP');
  function read(input){
    const raw=input.value.trim();
    if(!/^\d+$/.test(raw))return NaN;
    const n=Number(raw);
    return Number.isSafeInteger(n)?n:NaN;
  }
  function update(){
    const chosen=daily.value.trim();
    choices.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.riceQuantityChoice===chosen)));
    const inputs=[daily,days,stock];
    const values=inputs.map(read);
    const calc=countOnly(values[0],values[1],values[2]);
    inputs.forEach((input,i)=>input.setAttribute('aria-invalid',String(
      !Number.isSafeInteger(values[i])||
      i===0&&(values[i]<1||values[i]>24)||
      i===1&&(values[i]<1||values[i]>90)||
      i===2&&(values[i]<0||values[i]>100000)
    )));
    result.hidden=!calc;
    error.hidden=!!calc;
    if(!calc)return;
    root.querySelector('[data-rice-quantity-needed]').textContent=fmt(calc.needed)+'食';
    root.querySelector('[data-rice-quantity-shortage]').textContent=fmt(calc.shortage)+'食';
    root.querySelector('[data-rice-quantity-boxes]').textContent=fmt(calc.boxes)+'箱';
    root.querySelector('[data-rice-quantity-leftover]').textContent=fmt(calc.leftover)+'食';
    root.querySelector('[data-rice-quantity-summary]').textContent=calc.noBuy
      ?'今は買い足し不要です。手持ちの'+fmt(values[2])+'食で予定分をまかなえます。'
      :'必要'+fmt(calc.needed)+'食。手持ちを差し引くと'+fmt(calc.shortage)+'食不足します。'
       +'24食入りを選ぶ場合、'+fmt(calc.boxes)+'箱分が必要です。';
  }
  [daily,days,stock].forEach(input=>{
    input.addEventListener('input',update);
    input.addEventListener('change',update);
  });
  choices.forEach(button=>button.addEventListener('click',()=>{
    const n=Number(button.dataset.riceQuantityChoice);
    if(![1,2,3,4].includes(n))return;
    daily.value=String(n);update();
  }));
  form.addEventListener('submit',event=>{event.preventDefault();update();});
  update();
})();
