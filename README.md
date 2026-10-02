# food-cost-jp

食品を「表示価格」ではなく、容量・本数・食数をそろえた単価で比較する静的サイトです。

比較カテゴリ：
- パックご飯: 1食あたり / 100gあたり
- 米: 1kgあたり
- 炭酸水: 1Lあたり / 1本あたり
- オートミール: 100gあたり / 1kgあたり
- ミネラルウォーター: 1Lあたり / 1本あたり
- 乾燥スパゲッティ系パスタ: 100gあたり / 1kgあたり
- グラノーラ: 100gあたり / 1kgあたり
- レトルトカレー: 1食あたり / 100gあたり
- 即席袋ラーメン: 1食あたり
- 通常サイズのカップラーメン: 1食あたり

新カテゴリは安全な送料込み候補3件以上のときだけ売り場・Finderに表示します。掲載不足のページはnoindexとし、sitemapから除外します。

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
- `RAKUTEN_AFFILIATE_ID`（公開ビルドでは必須）

公開ワークフローのGA4測定IDは `GA_MEASUREMENT_ID` 環境変数に設定しています。ローカル生成では同名の環境変数で指定できます。

楽天Web Serviceの `RAKUTEN_APPLICATION_ID` / `RAKUTEN_ACCESS_KEY` は食品サイト専用アプリの値を使用し、`RAKUTEN_AFFILIATE_ID` は他サイトと共通で運用します。

## GitHub Pages
Settings > Pages > Build and deployment は現在の `Deploy from a branch` / `main` / `/ (root)` を使用します。楽天データ取得・品質判定・UI検査をActionsで行い、検証済み生成物のコミットからPagesが公開します。直接deploy-pagesを同時実行しないため二重公開の競合を防ぎます。

`.github/workflows/deploy-pages.yml` は main 更新時と毎日 05:30 JST にサイトを再生成します。

## Analytics
日用品版と共通化しやすいイベント名を使います。GA4の測定IDは `GA_MEASUREMENT_ID` からビルド時に注入します。

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
3. 次の食品は数量と食品タイプを検証し、安全な送料込み候補を確保してから追加
4. daily / pet / baby / food で単価計算・analytics schemaを共通化

## マルシェの入口と発見棚

トップは「お得 / 買い方の相談 / 買うものが決まっている」の3入口から始まります。相談の場合だけ詳細買い方を表示し、内部のcheap / large / small / budget / storage / knownは維持しています。発見棚とFinderは大きな写真と紙の単価値札、比較一覧は小画像と数値を優先します。

追加イベント：`hero_primary_cta`、`entry_route_select`（deal / advisor / known）。`shopping_intent_select`、`category_select_after_intent`、`market_shelf_view`、`market_shelf_product_click`、`finder_complete`と既存の楽天クリックイベントを維持。

オフラインUI確認：

```bash
python scripts/render_snapshot.py
python scripts/validate_generated_site.py site
npm ci --ignore-scripts
npm test
```

スナップショット再生は保存済み商品を現在の品質ルールで再判定します。価格確認日時を更新せず、楽天APIにもアクセスしません。

## 公開前の品質ゲート

毎日の公開はPythonテスト、実データ生成、生成物検証、UIテストがすべて成功した場合だけ行います。API取得失敗、カテゴリ消失・商品数急減、数量・単価の不整合、重複商品、楽天リンク欠落、内部リンク・canonical・sitemap・構造化データの異常は公開を止め、直前の公開サイトを維持します。

カテゴリとガイドの発見導線は送料込み商品3件以上を条件とします。少数になった既存ガイドはURLを残してnoindexとし、同じ商品集合のガイドはcanonicalを統合します。今日の棚だけは最安値の5%以内の上位候補を日替わりにしますが、値下がり商品を優先し、単価ランキングは変更しません。

保存・比較の楽天導線は `saved_modal` / `compare_modal` / `saved_watch` を `conversion_source` に記録します。保存時の数量・価格は最新データで更新し、現在確認できない商品の古い購入リンクは無効にします。`?test=1` は最初のページ閲覧から運営者テストとして記録されます。

Search Consoleではクエリとページを組み合わせ、表示回数・クリック・CTR・平均順位を確認します。十分な表示がある平均順位5〜20位を優先し、データがない段階では推測による記事・カテゴリの大量追加をしません。

[設計・公開確認記録](docs/discovery-market.md)

[カテゴリ拡張の対象と品質ルール](docs/category-expansion.md)
