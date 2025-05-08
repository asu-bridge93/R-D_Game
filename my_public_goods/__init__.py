from otree.api import *


doc = """
Your app description
"""

# 定数を格納するクラス
class C(BaseConstants):
    NAME_IN_URL = 'my_public_goods'
    PLAYERS_PER_GROUP = 4
    NUM_ROUNDS = 1
    ENDOWMENT = cu(1000)
    MULTIPLIER = 2

# サブセッションの設定
class Subsession(BaseSubsession):
    pass

# グループの設定
class Group(BaseGroup):
    total_contribution = models.CurrencyField() # 全員の投資額の合計
    individual_share = models.CurrencyField() # 公共財から得られる1人あたりの利益

# プレイヤーの設定
class Player(BasePlayer):
    contribution = models.CurrencyField(
        min=0, # 投資額の最小値
        max=C.ENDOWMENT, # 投資額の最大値
        label='公共財にいくら投資しますか?',
    )


# ページの設定
class MyPage(Page):
    form_model = 'player'
    form_fields = ['contribution']

# 結果の待ち時間ページ
class ResultsWaitPage(WaitPage):
    after_all_players_arrive = 'set_payoffs' # 全員が到着したら下のset_payoffsを実行

# 結果のページ
class Results(Page):
    pass

# ページの順番
page_sequence = [MyPage, ResultsWaitPage, Results]

# 利得の計算
def set_payoffs(group):
    players = group.get_players() # グループのプレイヤーを取得
    contributions = [p.contribution for p in players] # 各プレイヤーの投資額を取得
    group.total_contribution = sum(contributions) # 全員の投資額の合計
    group.individual_share = (
        group.total_contribution * C.MULTIPLIER / C.PLAYERS_PER_GROUP # 公共財から得られる1人あたりの利益
    )
    for player in players:
        player.payoff = C.ENDOWMENT - player.contribution + group.individual_share # 利得の計算
