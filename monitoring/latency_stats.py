"""Small fixed histogram for long term latency percentiles."""

from math import ceil


LATENCY_BUCKETS_MS = (1, 5, 10, 20, 30, 40, 50, 75, 100, 150, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000, 10000, 30000, 60000)


def latency_bucket(value):
    for bound in LATENCY_BUCKETS_MS:
        if value <= bound:
            return str(bound)
    return "over"


def add_latency(histogram, value, count=1):
    key = latency_bucket(value)
    histogram[key] = histogram.get(key, 0) + count


def merge_histograms(target, source):
    for key, count in source.items():
        target[key] = target.get(key, 0) + count


def p95_upper_bound(histogram):
    total = sum(histogram.values())
    if not total:
        return None
    rank = ceil(total * 0.95)
    seen = 0
    for bound in (*LATENCY_BUCKETS_MS, "over"):
        seen += histogram.get(str(bound), 0)
        if seen >= rank:
            return bound if bound != "over" else ">60000"
    return None
