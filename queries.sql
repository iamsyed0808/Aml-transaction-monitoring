-- Structuring: 3+ cash deposits of $8,000-$9,999 within a rolling 3-day window
SELECT DISTINCT acct FROM (
  SELECT acct, day, SUM(n) OVER (PARTITION BY acct ORDER BY day RANGE BETWEEN 2 PRECEDING AND CURRENT ROW) AS s
  FROM (SELECT acct, day, COUNT(*) AS n FROM tx
        WHERE type = 'cash_in' AND amount BETWEEN 8000 AND 9999.99 GROUP BY acct, day)
) WHERE s >= 3;

-- Rapid pass-through: same-day inflow >= $10k with 90%+ leaving the same day
SELECT i.acct, i.day, i.inflow, o.outflow FROM
 (SELECT acct, day, SUM(amount) inflow FROM tx WHERE type IN ('ach_in','cash_in','wire_in') GROUP BY acct, day) i
 JOIN (SELECT acct, day, SUM(amount) outflow FROM tx WHERE type IN ('ach_out','cash_out','wire_out') GROUP BY acct, day) o
 ON i.acct = o.acct AND i.day = o.day
WHERE i.inflow >= 10000 AND o.outflow >= 0.9 * i.inflow;

-- High-risk jurisdiction wires >= $5k
SELECT acct, COUNT(*) wires, SUM(amount) total FROM tx
WHERE type LIKE 'wire%' AND country IN ('IR','KP','SY','MM') AND amount >= 5000 GROUP BY acct;
