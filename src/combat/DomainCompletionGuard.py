"""Stop domain macros on confirmed reward text, including animation-safe waits."""
import re
import time


class DomainCompletionGuard:
    domain_reward_text = None

    def combat_once(self, *args, **kwargs):
        self._domain_combat_active = True
        self._domain_polling = False
        self._domain_next_poll = 0.0
        self._domain_reward_hits = 0
        self._domain_first_reward = None
        self._domain_confirmed_elapsed = None
        try:
            return super().combat_once(*args, **kwargs)
        finally:
            self._domain_combat_active = False
            self._domain_polling = False
            self._domain_reward_hits = 0

    def load_chars(self, *args, **kwargs):
        result = super().load_chars(*args, **kwargs)
        for char in self.chars or []:
            if char is None or getattr(char, '_domain_wait_wrapped', False):
                continue
            original = getattr(char, 'macro_wait', None)
            if callable(original):
                char.macro_wait = self._wrap_domain_wait(original)
                char._domain_wait_wrapped = True
        return result

    def _wrap_domain_wait(self, original):
        def guarded_wait(seconds):
            if not getattr(self, '_domain_combat_active', False) or seconds <= 0:
                return original(seconds)
            deadline = time.monotonic() + seconds
            while True:
                self.check_domain_completion()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                original(min(0.1, remaining))
        return guarded_wait

    def next_frame(self):
        frame = super().next_frame()
        self.check_domain_completion(frame=frame)
        return frame

    def sleep(self, seconds):
        self.check_domain_completion()
        result = super().sleep(seconds)
        self.check_domain_completion()
        return result

    def check_domain_completion(self, frame=None):
        if (not self.domain_reward_text or not getattr(self, '_domain_combat_active', False)
                or not self._in_combat or getattr(self, '_domain_polling', False)):
            return
        now = time.monotonic()
        if now < self._domain_next_poll:
            return
        self._domain_next_poll = now + 0.6
        self._domain_polling = True
        try:
            if frame is None:
                frame = super().next_frame()
            if frame is None:
                self._domain_reward_hits = 0
                self._domain_first_reward = None
                return
            # Only the persistent objective in the left HUD. No red-bar absence
            # or animation/HUD disappearance is interpreted as victory.
            boxes = self.ocr(0.0, 0.20, 0.24, 0.35, frame=frame,
                             match=self.domain_reward_text, threshold=0.95)
            if not boxes:
                self._domain_reward_hits = 0
                self._domain_first_reward = None
                return
            if not self._domain_reward_hits:
                self._domain_first_reward = now
                self.log_info('domain completion candidate: reward objective visible')
            self._domain_reward_hits += 1
            if self._domain_reward_hits < 2:
                return
            self._domain_combat_active = False
            self._domain_confirmed_elapsed = now - self._domain_first_reward
            self.log_info(f'domain completion confirmed: interrupt combo after '
                          f'{now - self._domain_first_reward:.2f}s from first reward frame')
            self.screenshot('domain_completion_confirmed')
            self._stop_completed_domain_combat()
        finally:
            self._domain_polling = False


SIMULATION_REWARD_TEXT = re.compile(r'^(?:领取奖励|領取獎勵|Claim Rewards?)$', re.IGNORECASE)
