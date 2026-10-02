# 商品を見たくなる入口と発見棚

## 監査・設計
既存の発見棚は最大115px、スマホは横添え76pxの写真で、商品名・情報が先に目に入る。6択が買い方の細かな違いを初回から求めていた。

Hero → 3入口（お得 / 相談 / 決まっている）→ 必要な詳細 → 写真主体の商品棚 → 単価で比較。4カテゴリは後段の売り場で維持。相談のみ large/small/budget/storage を表示、dealはcheap、knownはカテゴリ選択後cheapへ。内部ロジック・URL・localStorageは互換維持。

## カード
発見棚・Finderは写真220px領域（実画像188px）、スマホ200px領域（180px画像）。値札→商品名→価格・量→理由。楽天の同一商品サムネイルのみ640px版を使用し、内容の加工は行わない。カテゴリTop3は中サイズ（PC160px / スマホ125px）、4位以下は小画像の比較一覧を維持。価格履歴は閉じた状態。画像寸法と固定領域でCLS対策。

## 計測・検証
hero_primary_cta、entry_route_select（deal/advisor/known）を追加。既存のshopping_intent_select、category_select_after_intent、market_shelf_view、market_shelf_product_click、finder_complete、affiliate_clickおよび旧イベントを維持。

Python 57件、JS操作7件成功。PR #5をマージ。公開PCと390×844のiframeで3入口、相談4買い方、known4食品、全4売り場、写真寸法、保存・比較・7/30日履歴・楽天遷移を実操作確認。実機SafariではなくChromeのiPhone相当幅。

公開写真：PC188px、スマホ180px。画像原寸400〜640pxを確認。スマホ発見カード約647px、横棚343px中のカード309pxで次の商品が見える。Top3画像125px、4位以下76pxで横はみ出しなし。

2026-10-02 18:11 JSTの掲載126商品を、適格性・数量再解析・単価再計算・同一店舗内の実質重複の観点で監査、問題0件。21ページのcanonical、55件のJSON-LDを検証。

Actions：PR検証36988268414、main検証36988347943、ライブ取得/公開36988348081、生成物Pages36988387822はすべてsuccess。取得・分類・除外・Secrets・Pages競合対策は変更なし。GA4送信コードをテストし、管理画面での着信確認は未実施。

確認用noindexページは検証終了後に削除。画像証跡はdocs/verification/food-discovery-desktop-20261002.jpg、food-three-entries-phone-20261002.jpg。
