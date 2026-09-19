# food-cost-jp

食品を「表示価格」ではなく、容量・本数・食数をそろえた単価で比較する静的サイトです。

MVP:
- パックご飯: 1食あたり / 100gあたり
- 米: 1kgあたり
- 炭酸水: 1Lあたり / 1本あたり
- オートミール: 100gあたり / 1kgあたり

## 比較方針
- 楽天市場APIの商品価格・容量表記から単価を自動計算
- `postageFlag=0` の商品だけを「送料込み比較」に使用
- 送料別商品の送料額は推測せず、別枠の参考単価として表示
- 定期購入・初回限定・会員限定は通常価格ランキングから除外
- クーポン・ポイントは通常単価へ勝手に反映しない
- 数量を安全に読み取れない商品、選択式で容量が曖昧な商品は除外
- 価格確認日時を表示し、最新価格は販売ページで確認

## GitHub Secrets
Actions > Secrets and variables > Actions で以下を登録します。

- `RAKUTEN_APPLICATION_ID`
- `RAKUTEN_ACCESS_KEY`
- `RAKUTEN_AFFILIATE_ID`（推奨）
- `GA_MEASUREMENT_ID`（GA4を使う場合）

## GitHub Pages
Settings > Pages > Build and deployment > Source を `GitHub Actions` にします。

`.github/workflows/deploy-pages.yml` は main 更新時と毎日 05:30 JST にサイトを再生成します。

## Analytics
日用品版と共通化しやすいイベント名を使います。

- `affiliate_click`
- `product_result_click`
- `comparison_filter_use`
- `comparison_sort`
- `same_product_rakuten_click`（将来用）

主なパラメータ:
`site_id`, `category_id`, `product_id`, `product_name`, `affiliate`, `comparison_metric`, `unit_price`, `rank`, `shipping_status`, `conversion_source`, `click_position`, `operator_test`

運営者テストは公開URLへ `?test=1` を付けると有効、`?test=0` で解除します。

## ローカルテスト

```bash
python -m unittest discover -s tests -v
```

実サイト生成には楽天APIの環境変数が必要です。

## 次の拡張
1. GSCで表示回数が出たカテゴリだけ検索条件・商品数を増やす
2. JAN / Product ID で同一商品を安全に紐付け、容量・セット違い比較を追加
3. 水・コーヒーは日用品版との重複を整理してから食品版へ移管
4. daily / pet / baby / food で単価計算・analytics schemaを共通化
