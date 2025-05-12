from otree.api import *
import random


doc = """
R&D Investment Game - Companies make decisions on R&D investments with different reward conditions.
"""


class Constants(BaseConstants):
    name_in_url = 'r_and_d_game_spillover'
    players_per_group = 4
    num_rounds = 5  # 最大5回の投資決定を行う
    
    # 各プレイヤーの初期カード枚数
    cards_per_player = 5
    # カード1枚の価値（億円）
    card_value = 50
    # 成功時の報酬（億円）
    success_reward = 1500
    # SpillOver条件での失敗時の報酬（億円）
    spillover_reward = 1300
    
    # 成功確率の閾値
    success_thresholds = {
        (0, 4): 0,      # 0-4枚: 0%
        (5, 11): 1/3,   # 5-11枚: 33.3%
        (12, 16): 1/2,  # 12-16枚: 50%
        (17, 20): 2/3   # 17-20枚: 66.7%
    }


class Subsession(BaseSubsession):
    def creating_session(self):
        # セッションの設定を取得し各プレイヤーの参加者変数に保存
        spill_over = self.session.config.get('spill_over', True)
        for p in self.get_players():
            p.participant.vars['spill_over'] = spill_over


class Group(BaseGroup):
    total_cards_invested = models.IntegerField(min=0, max=Constants.players_per_group * Constants.cards_per_player)
    success_probability = models.FloatField()
    is_rd_successful = models.BooleanField()
    dice_roll = models.IntegerField(min=1, max=6)
    successful_player = models.IntegerField(min=0, max=Constants.players_per_group - 1, blank=True)
    
    def calculate_success_probability(self):
        """カードの合計枚数に基づいて成功確率を計算"""
        total = self.total_cards_invested
        for (min_cards, max_cards), probability in Constants.success_thresholds.items():
            if min_cards <= total <= max_cards:
                return probability
        return 0  # デフォルト値
    
    def set_payoffs(self):
        # グループ内の全員の投資額を集計
        player_investments = [p.cards_invested for p in self.get_players()]
        self.total_cards_invested = sum(player_investments)
        
        # 成功確率を決定
        self.success_probability = self.calculate_success_probability()
        
        # サイコロを振る
        self.dice_roll = random.randint(1, 6)
        
        # R&D成功判定
        if self.success_probability == 0:
            self.is_rd_successful = False
        else:
            threshold = self.success_probability * 6
            self.is_rd_successful = self.dice_roll <= threshold
        
        if self.is_rd_successful:
            # 成功した場合、どのプレイヤーが当選したかを決める
            if self.total_cards_invested > 0:
                weights = [p.cards_invested for p in self.get_players()]
                # 重みに比例してランダムに選ぶ
                if sum(weights) > 0:  # 0で割らないように確認
                    self.successful_player = random.choices(
                        range(Constants.players_per_group), 
                        weights=weights
                    )[0]
                else:
                    self.successful_player = random.randint(0, Constants.players_per_group - 1)
            else:
                self.successful_player = random.randint(0, Constants.players_per_group - 1)

            # 各プレイヤーの利益を計算
            for i, player in enumerate(self.get_players()):
                # ラウンドの累積投資額を計算
                player.calculate_total_investment()
                
                # セッション設定を取得
                is_spill_over = player.participant.vars.get('spill_over', True)
                
                if i == self.successful_player:
                    # 成功したプレイヤー
                    player.payoff = Constants.success_reward - player.total_investment
                else:
                    # 失敗したプレイヤー
                    if is_spill_over:
                        player.payoff = Constants.spillover_reward - player.total_investment
                    else:
                        player.payoff = -player.total_investment
                
                # プレイヤーの累積値を更新（Currencyからintに変換）
                previous_cumulative = 0
                if player.round_number > 1:
                    previous_cumulative = player.in_round(player.round_number - 1).cumulative_payoff
                
                # payoffをint型に変換して追加
                player.cumulative_payoff = previous_cumulative + int(player.payoff)
        else:
            # 失敗した場合は次のラウンドに進む（利益は確定しない）
            for player in self.get_players():
                player.calculate_total_investment()
                player.payoff = 0
                if player.round_number > 1:
                    player.cumulative_payoff = player.in_round(player.round_number - 1).cumulative_payoff
                else:
                    player.cumulative_payoff = 0


class Player(BasePlayer):
    cards_invested = models.IntegerField(min=0, max=Constants.cards_per_player, label="R&Dに投資するカードの枚数を選択してください（0〜5枚）")
    total_investment = models.IntegerField(min=0, initial=0)  # 累積投資額
    cumulative_payoff = models.IntegerField(initial=0)  # 累積利益
    
    def calculate_total_investment(self):
        """これまでのラウンドでの投資額の合計を計算"""
        # 現在のラウンドまでの投資額を合計
        total = 0
        for round_num in range(1, self.round_number + 1):
            # 各ラウンドでの投資額（カード枚数 * カード価値）
            total += self.in_round(round_num).cards_invested * Constants.card_value
        self.total_investment = total


# ページ定義
class Introduction(Page):
    """ゲームの説明ページ"""
    def is_displayed(self):
        return self.round_number == 1
    
    def vars_for_template(self):
        return {
            'is_spill_over': self.participant.vars.get('spill_over', True),
            'success_reward': Constants.success_reward,
            'spillover_reward': Constants.spillover_reward,
            'card_value': Constants.card_value,
            'cards_per_player': Constants.cards_per_player,
        }


class Investment(Page):
    """投資額を決定するページ"""
    form_model = 'player'
    form_fields = ['cards_invested']
    
    def vars_for_template(self):
        return {
            'round_number': self.round_number,
            'total_investment': self.in_round(self.round_number - 1).total_investment if self.round_number > 1 else 0,
            'cumulative_payoff': self.in_round(self.round_number - 1).cumulative_payoff if self.round_number > 1 else 0,
            'is_spill_over': self.participant.vars.get('spill_over', True),
        }


class WaitForAll(WaitPage):
    """全員の投資決定を待つ"""
    pass


class ResultsWaitPage(WaitPage):
    """結果を計算"""
    def after_all_players_arrive(self):
        self.group.set_payoffs()


class Results(Page):
    """結果表示ページ"""
    def vars_for_template(self):
        return {
            'round_number': self.round_number,
            'total_cards': self.group.total_cards_invested,
            'success_probability': int(self.group.success_probability * 100),
            'dice_roll': self.group.dice_roll,
            'is_successful': self.group.is_rd_successful,
            'successful_player_id': self.group.successful_player + 1 if self.group.is_rd_successful else None,
            'is_winner': self.id_in_group - 1 == self.group.successful_player if self.group.is_rd_successful else False,
            'is_spill_over': self.participant.vars.get('spill_over', True),
            'payoff': self.payoff,
            'total_investment': self.total_investment,
            'cumulative_payoff': self.cumulative_payoff,
            'success_reward': Constants.success_reward,
            'spillover_reward': Constants.spillover_reward,
        }


class FinalResults(Page):
    """最終結果表示ページ"""
    def is_displayed(self):
        # 最終ラウンドまたはR&Dが成功したら表示
        return self.round_number == Constants.num_rounds
    
    def vars_for_template(self):
        return {
            'cumulative_payoff': self.cumulative_payoff,
            'final_payoff': self.payoff,
            'total_investment': self.total_investment,
            'is_spill_over': self.participant.vars.get('spill_over', True),
        }


page_sequence = [
    Introduction,
    Investment,
    WaitForAll,
    ResultsWaitPage,
    Results,
    FinalResults,
]