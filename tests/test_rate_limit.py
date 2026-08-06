from web_scraper.rate_limit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_first_request_does_not_sleep():
    clk = FakeClock()
    rl = RateLimiter(1.0, clock=clk.time, sleep=clk.sleep)
    slept = rl.wait("https://example.com/a")
    assert slept == 0.0
    assert clk.sleeps == []


def test_second_request_to_same_host_sleeps_remaining_interval():
    clk = FakeClock()
    rl = RateLimiter(1.0, clock=clk.time, sleep=clk.sleep)
    rl.wait("https://example.com/a")
    clk.now += 0.3  # 300ms later
    slept = rl.wait("https://example.com/b")
    assert slept == 0.7
    assert clk.sleeps == [0.7]


def test_different_hosts_do_not_block_each_other():
    clk = FakeClock()
    rl = RateLimiter(5.0, clock=clk.time, sleep=clk.sleep)
    rl.wait("https://a.example.com/")
    rl.wait("https://b.example.com/")
    assert clk.sleeps == []


def test_zero_interval_disables_limiter():
    clk = FakeClock()
    rl = RateLimiter(0.0, clock=clk.time, sleep=clk.sleep)
    rl.wait("https://example.com/")
    rl.wait("https://example.com/")
    assert clk.sleeps == []


def test_already_past_interval_does_not_sleep():
    clk = FakeClock()
    rl = RateLimiter(1.0, clock=clk.time, sleep=clk.sleep)
    rl.wait("https://example.com/")
    clk.now += 5.0
    slept = rl.wait("https://example.com/")
    assert slept == 0.0
    assert clk.sleeps == []
