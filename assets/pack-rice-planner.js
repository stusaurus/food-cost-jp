/* Product-backed usage planner on the 24-meal comparison guide. */
(function () {
  'use strict';
  function calculate(count, price, mealsPerDay, periodDays = 30) {
    if (![count, price, mealsPerDay, periodDays].every(Number.isInteger) ||
        count < 1 || count > 10000 || price < 1 ||
        mealsPerDay < 1 || mealsPerDay > 24 || periodDays < 1 || periodDays > 366) {
      return null;
    }
    const mealsNeeded = mealsPerDay * periodDays;
    const boxes = Math.ceil(mealsNeeded / count);
    return {
      daysPerBox: count / mealsPerDay,
      mealsNeeded,
      boxes,
      purchaseTotal: boxes * price,
      remainingMeals: boxes * count - mealsNeeded,
      oneMealPrice: price / count,
      consumptionCost: mealsNeeded * price / count
    };
  }

  // Keep the established stock-free formula intact for existing integrations.
  // Stock is an explicit, non-persisted user input in meal units, not boxes.
  function calculateWithStock(count, price, mealsPerDay, stockMeals = 0, periodDays = 30) {
    const baseline = calculate(count, price, mealsPerDay, periodDays);
    if (!baseline || !Number.isSafeInteger(stockMeals) ||
        stockMeals < 0 || stockMeals > 100000) return null;
    const shortage = Math.max(0, baseline.mealsNeeded - stockMeals);
    const boxes = Math.ceil(shortage / count);
    return {
      ...baseline,
      stockMeals,
      shortage,
      boxes,
      purchaseTotal: boxes * price,
      remainingMeals: stockMeals + boxes * count - baseline.mealsNeeded,
      consumptionCost: shortage * price / count,
      noBuy: boxes === 0
    };
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { calculate, calculateWithStock };
  }
  if (typeof document === 'undefined') return;

  const root = document.querySelector('[data-rice-planner]');
  if (!root) return;
  const input = root.querySelector('#rice-meals-day');
  const mealChoices = [...root.querySelectorAll('[data-rice-meal-choice]')];
  const stockInput = root.querySelector('[data-rice-stock-input]');
  const select = root.querySelector('[data-rice-planner-product]');
  const form = root.querySelector('[data-rice-planner-form]');
  const results = root.querySelector('[data-rice-planner-results]');
  const error = root.querySelector('[data-rice-planner-error]');
  const shop = root.querySelector('[data-rice-planner-buy]');
  const lookup = name => root.querySelector('[data-rice-' + name + ']');
  const yen = value => '¥' + Number(value).toLocaleString('ja-JP', {
    minimumFractionDigits: Number.isInteger(value) ? 0 : 1,
    maximumFractionDigits: 1
  });
  const formattedDays = n => n.toLocaleString('ja-JP', { maximumFractionDigits: 1 }) + '日';
  const validRakuten = url => {
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'https:' &&
        (parsed.hostname === 'rakuten.co.jp' || parsed.hostname.endsWith('.rakuten.co.jp'));
    } catch (_) { return false; }
  };

  function update(track) {
    const rawMeal = input.value.trim();
    mealChoices.forEach(button => button.setAttribute(
      'aria-pressed', String(rawMeal === button.dataset.riceMealChoice)
    ));
    const option = select.selectedOptions[0];
    const raw = input.value.trim();
    const used = /^\d+$/.test(raw) ? Number(raw) : NaN;
    const stockRaw = stockInput.value.trim();
    const stockMeals = /^\d+$/.test(stockRaw) ? Number(stockRaw) : NaN;
    const count = Number(option?.dataset.count);
    const price = Number(option?.dataset.price);
    const data = calculateWithStock(count, price, used, stockMeals);
    const dest = option?.dataset.productUrl;
    const valid = Boolean(data && dest && validRakuten(dest));
    results.hidden = !valid;
    error.hidden = valid;
    input.setAttribute('aria-invalid', Number.isInteger(used) && used >= 1 && used <= 24 ? 'false' : 'true');
    stockInput.setAttribute('aria-invalid', Number.isSafeInteger(stockMeals) && stockMeals >= 0 && stockMeals <= 100000 ? 'false' : 'true');
    if (!valid) { shop.hidden = true; return; }

    lookup('days').textContent = formattedDays(data.daysPerBox);
    lookup('shortage').textContent = data.shortage.toLocaleString('ja-JP') + '食';
    lookup('recommendation').textContent = data.noBuy
      ? '今は買い足し不要です。手持ちの' + stockMeals.toLocaleString('ja-JP') + '食で予定分をまかなえます。'
      : '手持ちを差し引くと' + data.shortage.toLocaleString('ja-JP') + '食不足します。購入時は' + data.boxes.toLocaleString('ja-JP') + '箱分の金額が必要です。';
    lookup('boxes').textContent = data.boxes.toLocaleString('ja-JP') + '箱';
    lookup('purchase').textContent = yen(data.purchaseTotal);
    lookup('leftover').textContent = data.remainingMeals.toLocaleString('ja-JP') + '食';
    lookup('unit').textContent = yen(data.oneMealPrice);
    const grams = Number(option.dataset.grams);
    lookup('detail').textContent =
      '1食 ' + grams.toLocaleString('ja-JP') + 'g。買い足し対象の' +
      data.shortage.toLocaleString('ja-JP') + '食分の価格換算は' +
      yen(data.consumptionCost) + '。箱単位の購入総額とは異なります。';

    shop.hidden = data.noBuy;
    shop.href = dest;
    shop.dataset.productId = option.dataset.productId;
    shop.dataset.productName = option.dataset.productName;
    shop.dataset.unitPrice = option.dataset.unitPrice;
    shop.dataset.rank = option.dataset.rank;

    if (track && typeof window.foodCostTrack === 'function') {
      // Do not transmit household meal counts or other numeric user inputs.
      window.foodCostTrack('usage_planner_use', {
        category_id: 'pack-rice',
        page_path: location.pathname,
        tool_id: 'pack_rice_24_meals',
        input_valid: true,
        product_id: option.dataset.productId
      });
    }
  }

  // The legacy fixed "shopping memo" button must not cover calculator results.
  const floatingMemo = document.querySelector('.saved-fab');
  if (floatingMemo && typeof IntersectionObserver !== 'undefined') {
    const observer = new IntersectionObserver(entries => {
      const occludes = entries.some(entry => entry.isIntersecting);
      floatingMemo.classList.toggle('rice-planner-occluded', occludes);
      if (occludes) {
        floatingMemo.setAttribute('aria-hidden', 'true');
        floatingMemo.setAttribute('tabindex', '-1');
      } else {
        floatingMemo.removeAttribute('aria-hidden');
        floatingMemo.removeAttribute('tabindex');
      }
    }, { rootMargin: '-15px 0px -15px 0px', threshold: 0 });
    observer.observe(root);
  }

  mealChoices.forEach(button => button.addEventListener('click', () => {
    const meal = Number(button.dataset.riceMealChoice);
    if (![1, 2, 3, 4].includes(meal)) return;
    input.value = String(meal);
    update(true);
  }));
  form.addEventListener('submit', e => { e.preventDefault(); update(true); });
  input.addEventListener('input', () => update(false));
  stockInput.addEventListener('input', () => update(false));
  stockInput.addEventListener('change', () => update(true));
  input.addEventListener('change', () => update(true));
  select.addEventListener('change', () => update(true));
  update(false);
})();
