﻿                 CardWirth Py Lite
                  Ver 4.0α1(04)
                  フォーク制作者：暗黒騎士<ankkksあっとoutlook.jp>
                  wiki：https://www65.atwiki.jp/pylite/
                  開発：https://bitbucket.org/akkw/cardwirthpy-lite/
                  動作確認環境：Windows 7/10 64bit
---------------------------------------------------------------------------

これは：CardWirthPy / Rebootからのさらなるフォーク(派生版)です。
PyRebootとの方向性の違いにより分岐(2016/11/21版)、以降Rebootの更新を選択的に取り込みつつ独自の変更を含みます。

PyLiteの目標

「CardWirth再現性の向上」
　　　スキン以外の外観/挙動を、バグも含めCardWirth1.28/1.50に可能な限り近づける。
「ゆとり化(ライト化)」
　　　フォルダ・ファイル構成・オリジナル文言をシンプル・軽量化し、面倒な手順を減らしてすぐ遊べるようにする。
「より多くのシナリオ」
　　　対応シナリオ(規格)を最大限増やす。現状はマイナー仕様・バグ利用シナリオのみ。

--------------------------------------------------------------------------

●PyLiteの更新情報

Ver4.0a
19.07.27 メッセージの選択肢がフォーカスされない(下記のエンバグ)
19.07.27 シナリオ中、キーでメニューカードをフォーカスできない
19.07.27 10以上のボーナス/ペナルティの文言「最大」を削除するようにした(CW準拠)
19.07.26 宿新規作成時にファイル探索エラー
19.07.26 デフォルトDPIのカーソルをWindows10デフォルトサイズに調整
19.07.24 設定、カード操作、キャラ情報ダイアログで一部処理を内包表記(高速化を期待) 
19.07.23 種族が1種でもあるスキンでスキン外種族の表示文字色を青に変更
19.07.23 クーポンの得点下限値が9921億になっていた(-21億が正)
19.07.23 能力変化モーションの有効条件の判定式に対象の合計値が使われていた(Reboot4/CW準拠)
19.07.22 スキンで独自エリア、WSN追加効果音を使用可能にした(Reboot4)
19.07.21 キャストの画像登録系に外部ファイル参照ボタンを追加(Reboot4)
19.07.21 デザイン変更にも「自動」ボタンを追加(Reboot4、オプションで無効化可能)
19.07.20 デバッガでBGM再生と保存された状態変数DLGが機能していなかった
19.07.19 キャラ情報DLGの背景カラー変更直後の描画が遅延する場合があった
19.07.17 スキンで状態変数とパッケージを使用可能にした(Reboot4)
19.07.13 キャラクター情報ダイアログの背景カラー変更機能をテスト実装(Reboot4)
              Rebootより明度上限を若干高くしています(128→192)
              同梱は行っていませんが、Reboot付属の見本色(BackColors.xml)も使用可能です。
19.07.12 バトル中、デバッグモードへの切り替えができないようにした
19.07.10 Pyスキンバージョン"12"に対応(Reboot4)
               Reboot付属Classicスキンの素材拡張子がオリジナルのwav/bmpからogg/pngに変更されているため、
               Pyで1.50用シナリオを作ろうとすると拡張子が消滅する場合がある問題への対処に付随する変更です。
               なお、PyLite付属のClassicスキンのリソースはwav/bmpのままであるため、通常この拡張子問題は起こりません。
19.07.08 1.30以前の互換モードを除き、JPG背景セルの透過設定が無効になるようにした(1.50準拠/Reboot3)
19.07.07 α1公開
19.07.02 現時点までのWSN4の機能に対応し、内部バージョンを4.0に変更 
19.07.01 「イベント中にステータスバーの色を変える」を有効にした時、再起動しないと反映されていなかった
19.06.26 簡易作成の能力型を指定したPCに解説が表示されるようにした (Reboot4/CW準拠)
19.06.24 本来アルバム移動時に失われる「最大ライフ」「対カード属性」を内部的に記録するようにした (Reboot4)
19.06.23 ゲームオーバー画面での操作を一部有効にした(Reboot4)
               ゲームオーバー画面でのF9については、PyLiteではCW準拠のため「無効」が仕様となります。 
19.06.23 シナリオ中にF8キーで添付テキストダイアログを開くようにした(Reboot4)
19.06.23 通知オプション「ステータスバーに情報カードの所有枚数を表示」を追加(デフォルトで有効)
               情報カード枚数を常に通知しているPy独自機能を無効化できるようにしました。
               また、オプション有効時は1枚以上所持している時の通知が常に表示されるように変更。
19.06.22 ファイル名に使用できない文字を含む名前のキャラクターのイメージを変更するとエラー(Reboot3.4)
19.06.21 宿選択画面で最後に選択した順で宿がソートされるようにした(Reboot4)
               従来型の並びは整列＞名前で行えます。
19.06.19 宿の看板画像の変更機能を追加(Reboot4)
               宿選択画面の拡張から変更できます。
19.06.19 メッセージを最速以外で表示している時、句読点等の後にウェイトを挿入(Reboot4/CW準拠)
19.06.18 スキンでのスクリーンショットの背景画像「SCREENSHOT_HEADER」に対応(Reboot4)
　　　　　それに伴いフォント指定「撮影情報」を「スクリーンショット」に改称、デフォルトを可変幅明朝に変更

Ver3.2
19.06.23 3.2としてバージョンアップ
19.06.23 睡眠者無効の能力判定が正常に行われていなかった(3.1のエンバグ) 
19.06.23 3.1においてバージョン判定クーポンの更新が行われていなかった
19.06.22 デバッガで情報カード変更に使用するアイコンをCardWirthの状態変数ｲﾝｽﾍﾟｸﾀのものに差替

Ver3.1
19.06.17 3.1としてバージョンアップ 
19.05.26 @で始まる縦書き用大体フォントが探索されない(Reboot3.4)
19.05.25 メッセージ表示中に表示速度設定等を変更した場合にメッセージログの選択肢が増殖(Reboot3.4)
19.05.18 WSN3：スキル/アイテム/召喚獣所持分岐で選択カードにする機能の移植漏れ
19.05.18 WSN3：選択カードのチェック判定の移植漏れ(宿のカードコンバート可否判定に影響) 
19.05.16 Reboot4においても＠デバグが仕様として組みこまれたため仕様を合流

Ver3.0
19.05.15 正式公開

(Reboot)2018.03以降、開発環境に違いが生じたためRebootから移植した分を記載しています。

古いログ
https://www65.atwiki.jp/pylite/pages/4.html

--------------------------------------------------------------------------

●インストール/アンインストール
「CardWirthPyLite.exe」を起動して下さい。
Windowsのセキュリティ設定に引っかかる場合、右クリック→プロパティ→ブロックの解除。
アンインストールは、CWと同じくレジストリを使用しないのでフォルダごと削除でOKです。

・シナリオを沢山入れて重い場合
　　　　　設定＞シナリオ＞シナリオタイプ＞データベース構築を推奨。

・gdiplus.dllがない場合
　　　　　https://www7.atwiki.jp/nico_player/pages/16.html

・[スキンの自動生成ダイアログ]が出た場合
　　　　　スキンが入っていません。
　　　　「基本>本体」右のボタンからご使用のCardwirth1.20~1.50のエンジンexeを選択するか
　　　　　Data\Skinに直接スキンを入れてください。

・アップデート方法
　　　　　ファイルを全て上書きして下さい。
　　　　　機能追加がある場合、exeだけの更新だとエラーになることがあります。

・遊び方
　　　　　https://www65.atwiki.jp/pylite/pages/6.html


●互換性

[宿/スキン]
　PyRebootと同じくCardWirth 1.28-1.50の宿は変換・逆変換が可能です。
　宿/スキンデータの構造上はPyRebootと互換を損なうような変更(※)はしていないので、
　Py(1.1-2.3)の宿やスキンはそのままフォルダをコピーしてもほぼ問題なく動くと思います。
　動かなかったら教えて下さい。

　なにか問題が起こった場合は、一度Py→1.50→PyLiteというような変換を経れば大丈夫だと思います。
　(Py専用の諸々は初期化されますが)

[シナリオ]
　CW1.20～1.50仕様/WSN0～2(※)に対応します。NEXTシナリオは貼り紙に表示されません。
　バグやマイナー仕様の再現によって、対応シナリオが僅かに多い(確認している範囲で8本)点以外はPyと一緒です。
　
　※KC所持分岐についてはWSN形式でも1.50と同等の挙動をする点だけご注意ください。
　([アイテム]だけにチェックが付いている状態でも戦闘手札が検索されます)

●その他

レベルが上がらない
　PyLiteではデバッグモード(右下に鉛筆ボタンが表示)だと設定にかかわらずレベルアップできません。
　CardWirthのデバグ宿ではレベルアップしないため、意図的にそういう仕様にしています。
　一旦解除(Ctrl+D)してリューンなどに入って帰ってくればレベルアップします。

●対応できていない不具合(Rebootと同じ)

* ダイアログの開閉に遅延が起こる
　→Windowsの再起動
* サウンドフォントが一つもチェックされていないと音が鳴らない
　→存在するサウンドフォントだけにチェックをつけて下さい(デフォルトならそのままでOK)
* NEXT形式シナリオを含むフォルダを開くのが遅い
　→NEXT形式シナリオ(表示されない＆ドロップしてエラー音がなるシナリオ)は
　　可能であればフォルダから除外するのを推奨します

--------------------------------------------------------------------------

●独自の追加要素/変更点
　変更は多岐にわたるのでプレイ上、重要なものを一部抜粋します。

ショートカットキーの強化
##########################################################################
　全般　　　　　戻る・閉じる(BACKSPACE//(BACKSLASH))/削除(DELETE)
　拠点選択　　　新規宿(CTRL+N)
　キャラ選択　　新規登録(CTRL+N)/自動登録(CTRL+A)
　カード操作　　ゴミ箱に送る(DELETE)
　シナリオ選択　インストール(CTRL+I)/新規フォルダ(CTRL+N)/移動(CTRL+M)/名前の変更(CTRL+R)

　編集・設定　移動(CTRL+↑↓)/最上下へ移動(CTRL+HOME/END)/削除(DELETE)
　(設定ダイアログのサウンドフォント、デバッグモードのクーポン・ゴシップ・終了印・ブックマーク編集ダイアログ)
##########################################################################

CardWirth仕様再現の追加オプション
　そのまま再現すると別の問題が生じるなど、やむを得ないものにPyLite独自の互換オプションを設けています。

・フォント「カード名やタイトルを縁取りする」　CW準拠：無効
・シナリオ「CardWirth1.28由来のF9仕様を再現する」　CW準拠：有効※不具合が出るシナリオもあるので非推奨
・シナリオ「CardWirth1.50の変数=バグを再現する」　1.28：無効 / 1.50：有効(デフォルト)
・詳細「ホイールでカード選択と選択肢のフォーカス移動を行う」　CW準拠：無効

その他
Rebootにあり、Liteにない要素の詳細
https://www65.atwiki.jp/pylite/pages/24.html
Liteにあり、Rebootにない要素の詳細
https://www65.atwiki.jp/pylite/pages/18.html


--------------------------------------------------------------------------

●ライセンス
ソース及びアイコンはMITライセンス、PyLite.exe実行ファイルはGNU劣等一般公衆、CW由来の素材はgroupASKの規約に準じます。
各DLL及び著作権情報はlicense.txtを参照下さい。各ライセンスを満たす限り、再配布、再フォーク等は自由です。

