import random

from otree.api import (
    BaseConstants,
    BaseGroup,
    BasePlayer,
    BaseSubsession,
    Page,
    WaitPage,
    models,
)

doc = """
Your app description
"""


class C(BaseConstants):
    NAME_IN_URL = "two_stage_contest"
    PLAYERS_PER_GROUP = 2
    NUM_ROUNDS = 2
    INSTRUCTION_CONTENTS = "two_stage_contest/Instruction_contents.html"    

    ############### この部分を変更すること #################################
    # 報酬設定
    REWARDS = {
        "Winner_Rewards": [500, 1500],  # [Round 1, Round 2] で得られる報酬
        "Loser_Rewards": [0, 0],  # [Round 1, Round 2] で得られる報酬
    }
    ############### ここまで ############################################

    # HTML表示用に変数仮置き
    R11 = REWARDS["Winner_Rewards"][0]
    R12 = REWARDS["Winner_Rewards"][1]
    R21 = REWARDS["Loser_Rewards"][0]
    R22 = REWARDS["Loser_Rewards"][1]


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):    
    effort = models.IntegerField(
        min=0,
        label="投入するエフォートの大きさを入力して下さい。",
    )
    cost = models.IntegerField(
        initial=-1,  # 初期値は−1とし、before_next_page　で設定
    )
    reward = models.FloatField(initial=0)  # 得られた報酬を格納する変数
    win_flg = models.IntegerField(initial=-1)  # 0:負け, 1:引き分け, 2:勝ち


# 　FUNCTIONS
def creating_session(subsession: Subsession):
    num = subsession.session.num_participants
    subsession.session.vars["costs"] = [ random.randint(1, 100) for i in range(num) ]            


def effort_max(player: Player):
    return int(C.REWARDS["Winner_Rewards"][player.round_number - 1] / player.cost)


def set_payoffs(group: Group):
    for player in group.get_players():
        opponent = group.get_player_by_id(player.id_in_group % 2 + 1)
        player_effort_value = player.cost * player.effort
        opponent_effort_value = opponent.cost * opponent.effort

        if player.effort > opponent.effort:  # 勝者の場合
            if group.round_number == 1:  # 第一ラウンド
                if player_effort_value < 300:
                    player.reward = 350  # 500 - 150
                    opponent.reward = 150
                elif player_effort_value < 400:
                    player.reward = 450  # 500 - 50
                    opponent.reward = 50
                else:
                    player.reward = 500
                    opponent.reward = 0
            else:  # 第二ラウンド
                if player_effort_value < 1300:
                    player.reward = 1100  # 1500 - 400
                    opponent.reward = 400
                elif player_effort_value < 1400:
                    player.reward = 1400  # 1500 - 100
                    opponent.reward = 100
                else:
                    player.reward = 1500
                    opponent.reward = 0
            player.win_flg = 2  # Winner
            opponent.win_flg = 0  # Loser
        elif player.effort == opponent.effort:  # 引き分けの場合
            if group.round_number == 1:  # 第一ラウンド
                player.reward = 250  # 500 / 2
                opponent.reward = 250
            else:  # 第二ラウンド
                player.reward = 750  # 1500 / 2
                opponent.reward = 750
            player.win_flg = 1  # Tie
            opponent.win_flg = 1  # Tie
        else:  # 敗者の場合
            if group.round_number == 1:  # 第一ラウンド
                if opponent_effort_value < 300:
                    player.reward = 150
                    opponent.reward = 350  # 500 - 150
                elif opponent_effort_value < 400:
                    player.reward = 50
                    opponent.reward = 450  # 500 - 50
                else:
                    player.reward = 0
                    opponent.reward = 500
            else:  # 第二ラウンド
                if opponent_effort_value < 1300:
                    player.reward = 400
                    opponent.reward = 1100  # 1500 - 400
                elif opponent_effort_value < 1400:
                    player.reward = 100
                    opponent.reward = 1400  # 1500 - 100
                else:
                    player.reward = 0
                    opponent.reward = 1500
            player.win_flg = 0  # Loser
            opponent.win_flg = 2  # Winner

        # 利得の計算
        player.payoff = player.reward - player.cost * player.effort
        opponent.payoff = opponent.reward - opponent.cost * opponent.effort


# PAGES
class Instruction(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1  # Round 1だけこのページに入る


class Decision(Page):
    form_model = "player"
    form_fields = ["effort"]

    @staticmethod
    def is_displayed(player):        
        # 各プレイヤのcostの値をを保存
        player.cost = player.subsession.session.vars["costs"][player.id_in_subsession - 1]
        return True  # 前プレイヤがこのページに入る

    @staticmethod
    def vars_for_template(player):
        if player.round_number > 1:
            prev_player = player.in_round(player.round_number - 1)
            if prev_player.win_flg == 2:
                prev_state = "1位"
            elif prev_player.win_flg == 1:
                prev_state = "引き分け"
            else:
                prev_state = "2位"
            return dict(
                prev_effort=prev_player.effort,
                prev_state=prev_state,
            )
        else:
            return dict(
                prev_effort=-1,
                prev_state="",
            )


class ResultsWaitPage(WaitPage):
    after_all_players_arrive = "set_payoffs"


class Results(Page):
    @staticmethod
    def vars_for_template(player):
        total_payoff = 0
        for p in player.in_all_rounds():
            total_payoff += p.payoff

        if player.round_number > 1:
            prev_player = player.in_round(player.round_number - 1)
            if prev_player.win_flg == 2:
                prev_state = "1位"
            elif prev_player.win_flg == 1:
                prev_state = "引き分け"
            else:
                prev_state = "2位"
            return dict(
                prev_effort=prev_player.effort,
                prev_state=prev_state,
                total_payoff=total_payoff,
            )
        else:
            return dict(
                prev_effort=-1,
                prev_state="",
                total_payoff=total_payoff,
            )


page_sequence = [Instruction, Decision, ResultsWaitPage, Results]
