from otree.api import *

doc = """
繰り返し+割引ありの最後通牒ゲーム
プレイヤーAが提案者として始め、プレイヤーBが応答者として始めます。
合意に達するか10ラウンドが終了するまでゲームは続きます。
"""

class C(BaseConstants):
    NAME_IN_URL = 'practice'
    PLAYERS_PER_GROUP = 2
    NUM_ROUNDS = 10
    INITIAL_BUDGET = cu(1000)
    DISCOUNT_FACTOR = 0.8

class Subsession(BaseSubsession):
    def creating_session(self):
        # 初期化 - 全グループに対して実行
        for group in self.get_groups():
            if self.round_number == 1:
                # セッション変数の初期化
                # agreeはグループごとに異なる値を持つ必要があるため、グループIDをキーとして使用
                group.session.vars[f'agree_{group.id_in_subsession}'] = False
                group.session.vars[f'finished_{group.id_in_subsession}'] = False

class Group(BaseGroup):
    # 提案額
    proposal = models.CurrencyField(
        min=0,
        default=0,
        doc="提案者が提示する金額"
    )
    
    # 応答（受け入れるかどうか）
    accept = models.BooleanField(
        doc="応答者が提案を受け入れるかどうか"
    )
    
    def get_current_budget(self):
        # 現在のラウンドにおける予算額
        return C.INITIAL_BUDGET * (C.DISCOUNT_FACTOR ** (self.round_number - 1))
    
    def check_agreement_status(self):
        # このグループが既に合意に達しているかどうかを確認
        return self.session.vars.get(f'agree_{self.id_in_subsession}', False)
    
    def is_finished(self):
        # このグループがゲームを完了しているかどうかを確認
        return self.session.vars.get(f'finished_{self.id_in_subsession}', False)
    
    def set_agreement(self, value):
        # 合意状態を設定
        self.session.vars[f'agree_{self.id_in_subsession}'] = value
    
    def set_finished(self, value):
        # 完了状態を設定
        self.session.vars[f'finished_{self.id_in_subsession}'] = value

class Player(BasePlayer):
    # プレイヤーの役割を取得（各ラウンドで交代）
    def role(self):
        # プレイヤーAの場合
        if self.id_in_group == 1:
            # 奇数ラウンドでは提案者、偶数ラウンドでは応答者
            return 'proposer' if self.round_number % 2 == 1 else 'responder'
        # プレイヤーBの場合
        else:
            # 偶数ラウンドでは提案者、奇数ラウンドでは応答者
            return 'proposer' if self.round_number % 2 == 0 else 'responder'
            
    def get_role_display(self):
        if self.role() == 'proposer':
            return '提案者'
        else:
            return '応答者'
    
    # 合意後の最終的な獲得金額
    final_payoff = models.CurrencyField()

# ページクラス
class Proposer(Page):
    form_model = 'group'
    form_fields = ['proposal']
    
    def is_displayed(self):
        # すでに合意済みか完了済みの場合はページを表示しない
        if self.group.check_agreement_status() or self.group.is_finished():
            return False
        # 現在のプレイヤーが提案者の役割である場合のみ表示
        return self.role() == 'proposer'
    
    def vars_for_template(self):
        current_budget = self.group.get_current_budget()
        
        # 提案額がまだ設定されていない場合（初回表示時）は0とする
        proposal = self.group.field_maybe_none('proposal') or 0
        remainder = current_budget - proposal
        next_budget = current_budget * C.DISCOUNT_FACTOR
        
        return {
            'current_budget': current_budget,
            'proposal': proposal,
            'remainder': remainder,
            'next_budget': next_budget,
            'round_number': self.round_number,
            'role': self.get_role_display()
        }

class WaitForProposer(WaitPage):
    def is_displayed(self):
        # すでに合意済みか完了済みの場合はページを表示しない
        return not (self.group.check_agreement_status() or self.group.is_finished())
    
    title_text = "提案者の決定を待っています"
    body_text = "提案者があなたへの提案額を決めています。しばらくお待ちください。"

class Responder(Page):
    form_model = 'group'
    form_fields = ['accept']
    
    def is_displayed(self):
        # すでに合意済みか完了済みの場合はページを表示しない
        if self.group.check_agreement_status() or self.group.is_finished():
            return False
        # 現在のプレイヤーが応答者の役割である場合のみ表示
        return self.role() == 'responder'
    
    def vars_for_template(self):
        current_budget = self.group.get_current_budget()
        
        # 提案額がまだ設定されていない場合（初回表示時）は0とする
        proposal = self.group.field_maybe_none('proposal') or 0
        remainder = current_budget - proposal
        next_budget = current_budget * C.DISCOUNT_FACTOR
        
        return {
            'current_budget': current_budget,
            'proposal': proposal,
            'remainder': remainder,
            'next_budget': next_budget,
            'round_number': self.round_number,
            'role': self.get_role_display()
        }

class ResultsWaitPage(WaitPage):
    def is_displayed(self):
        # すでに合意済みか完了済みの場合はページを表示しない
        return not (self.group.check_agreement_status() or self.group.is_finished())
    
    def after_all_players_arrive(self):
        # 応答者が提案を受け入れた場合
        if hasattr(self.group, 'accept') and self.group.accept:
            self.group.set_agreement(True)
            
            current_budget = self.group.get_current_budget()
            # 提案額がまだ設定されていない場合は0とする
            proposal = self.group.field_maybe_none('proposal') or 0
            remainder = current_budget - proposal
            
            # 提案者と応答者を特定
            for p in self.group.get_players():
                if p.role() == 'proposer':
                    # 提案者は proposalを受け取る
                    p.final_payoff = proposal
                else: 
                    # 応答者は remainderを受け取る
                    p.final_payoff = remainder
        
        # 合意が成立した場合、ゲームを完了状態に設定
        if self.group.check_agreement_status():
            self.group.set_finished(True)

        # 最終ラウンドの場合、ゲーム完了とする
        if self.round_number == C.NUM_ROUNDS:
            self.group.set_finished(True)

class Results(Page):
    def is_displayed(self):
        # すべてのプレイヤーに結果を表示
        return True
    
    def vars_for_template(self):
        agreement = self.group.check_agreement_status()
        finished = self.group.is_finished()
        
        # 提案額がまだ設定されていない場合（初回表示時）は0とする
        proposal = self.group.field_maybe_none('proposal') or 0
        current_budget = self.group.get_current_budget()
        next_budget = current_budget * C.DISCOUNT_FACTOR
        
        vars_dict = {
            'agreement': agreement,
            'finished': finished,
            'round_number': self.round_number,
            'current_budget': current_budget,
            'next_budget': next_budget,
            'proposal': proposal,
        }
        
        if agreement:
            for p in self.group.get_players():
                if p.id_in_group == self.id_in_group:
                    vars_dict['final_payoff'] = p.field_maybe_none('final_payoff') or 0
        
        return vars_dict

page_sequence = [
    Proposer,
    WaitForProposer,
    Responder,
    ResultsWaitPage,
    Results
]