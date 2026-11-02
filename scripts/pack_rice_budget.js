/* 24食ガイド専用。数値はすべて検証済みの掲載商品と入力食数から計算する。 */
(function () {
  'use strict';
  var panel = document.querySelector('[data-pack-rice-budget]');
  if (!panel) return;
  var form = panel.querySelector('[data-budget-form]');
  var product = panel.querySelector('[data-budget-product]');
  var daily = panel.querySelector('[data-budget-daily]');
  var error = panel.querySelector('[data-budget-error]');
  var results = panel.querySelector('[data-budget-results]');
  var fields = {
    days: panel.querySelector('[data-budget-days]'),
    meals: panel.querySelector('[data-budget-month-meals]'),
    boxes: panel.querySelector('[data-budget-boxes]'),
    payment: panel.querySelector('[data-budget-payment]'),
    left: panel.querySelector('[data-budget-left]'),
    unit: panel.querySelector('[data-budget-unit]')
  };
  function fmt(value) {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  function yen(value) {
    return '¥' + Math.round(value).toLocaleString('ja-JP');
  }
  function compute() {
    var selected = product.selectedOptions[0];
    var amount = Number(selected && selected.dataset.price);
    var count = Number(selected && selected.dataset.count);
    var servings = Number(daily.value);
    var valid = Number.isFinite(amount) && amount > 0 &&
      Number.isInteger(count) && count === 24 &&
      daily.value.trim() !== '' && Number.isFinite(servings) &&
      servings >= 0.5 && servings <= 12 &&
      Math.abs(servings * 2 - Math.round(servings * 2)) < 1e-8;
    if (!valid) {
      error.textContent = '1日の平均食数を0.5〜12の範囲で、0.5食刻みで入力してください。';
      error.hidden = false;
      results.hidden = true;
      return;
    }
    error.textContent = '';
    error.hidden = true;
    var monthlyMeals = servings * 30;
    var boxes = Math.ceil(monthlyMeals / count);
    fields.days.textContent = fmt(count / servings) + '日';
    fields.meals.textContent = fmt(monthlyMeals) + '食';
    fields.boxes.textContent = String(boxes) + '箱';
    fields.payment.textContent = yen(boxes * amount);
    fields.left.textContent = fmt(boxes * count - monthlyMeals) + '食';
    fields.unit.textContent = yen(amount / count);
    results.hidden = false;
  }
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    compute();
  });
  product.addEventListener('change', compute);
  daily.addEventListener('input', compute);
  compute();
})();