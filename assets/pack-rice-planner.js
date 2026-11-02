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

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { calculate };
  }
  if (typeof document === 'undefined') return;

  const root = document.querySelector('[data-rice-planner]');
  if (!root) return;
  const input = root.querySelector('#rice-meals-day');
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
    const option = select.selectedOptions[0];
    const raw = input.value.trim();
    const used = /^\d+$/.test(raw) ? Number(raw) : NaN;
    const count = Number(option?.dataset.count);
    const price = Number(option?.dataset.price);
    const data = calculate(count, price, used);
    const dest = option?.dataset.productUrl;
    const valid = Boolean(data && dest && validRakuten(dest));
    results.hidden = !valid;
    error.hidden = valid;
    input.setAttribute('aria-invalid', valid ? 'false' : 'true');
    if (!valid) return;

    lookup('days').textContent = formattedDays(data.daysPerBox);
    lookup('boxes').textContent = data.boxes.toLocaleString('ja-JP') + '箱';
    lookup('purchase').textContent = yen(data.purchaseTotal);
    lookup('leftover').textContent = data.remainingMeals.toLocaleString('ja-JP') + '食';
    lookup('unit').textContent = yen(data.oneMealPrice);
    const grams = Number(option.dataset.grams);
    lookup('detail').textContent =
      '1食 ' + grams.toLocaleString('ja-JP') + 'g。30日間に使う' +
      data.mealsNeeded.toLocaleString('ja-JP') + '食分の価格換算は' +
      yen(data.consumptionCost) + '。箱単位の購入総額とは異なります。';

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

  form.addEventListener('submit', e => { e.preventDefault(); update(true); });
  input.addEventListener('input', () => update(false));
  input.addEventListener('change', () => update(true));
  select.addEventListener('change', () => update(true));
  update(false);
})();
