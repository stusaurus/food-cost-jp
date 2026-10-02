# 商品を見たくなる入口と発見棚

## 監査・設計
既存の発見棚は最大115px、スマホは横添え76pxの写真で、商品名・情報が先に目に入る。6択が買い方の細かな違いを初回から求めていた。

Hero → 3入口（お得 / 相談 / 決まっている）→ 必要な詳細 → 写真主体の商品棚 → 単価で比較。4カテゴリは後段の売り場で維持。相談のみ large/small/budget/storage を表示、dealはcheap、knownはカテゴリ選択後cheapへ。内部ロジック・URL・localStorageは互換維持。

## カード
発見棚・Finderは写真220px領域（実画像188px）、スマホ200px領域（180px画像）。値札→商品名→価格・量→理由。楽天の同一商品サムネイルのみ640px版を使用し、内容の加工は行わない。カテゴリTop3は中サイズ（PC160px / スマホ125px）、4位以下は小画像の比較一覧を維持。価格履歴は閉じた状態。画像寸法と固定領域でCLS対策。

## 計測・検証
hero_primary_cta、entry_route_select（deal/advisor/known）を追加。既存のshopping_intent_select、category_select_after_intent、market_shelf_view、market_shelf_product_click、finder_complete、affiliate_clickおよび旧イベントを維持。

ローカル Python 57件、JS操作7件成功。公開・品質・PC・390px確認は後続で記録。
