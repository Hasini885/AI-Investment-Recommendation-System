% Risk profile rules based on Age, Income, and Investment Goal

% 1. Students/Young Investors (High risk tolerance because of time horizon)
% This rule is now TOP priority.
risk_profile(high, Age, _, _) :- 
    Age =< 25.

% 2. Low Risk: Older users OR very low income (if not a young student)
risk_profile(low, Age, _, retirement) :- 
    Age > 45.
risk_profile(low, _, Income, _) :- 
    Income < 20000.

% 3. Medium Risk: Middle age with stable income
risk_profile(medium, Age, Income, _) :- 
    Age =< 50, Age > 30, Income >= 20000.

% 4. High Risk: Adult users with high income and wealth goals
risk_profile(high, Age, Income, wealth) :- 
    Age =< 35, Income > 50000.

% Default fallback
risk_profile(medium, _, _, _).


% Investment strategies with detailed allocations
strategy(low, "Safety First Portfolio", "60% Bonds, 20% FD, 10% Gold, 10% Large Cap Stocks").
strategy(medium, "Balanced Growth Portfolio", "40% Mutual Funds, 30% Blue-chip Stocks, 20% Index Funds, 10% Gold").
strategy(high, "Aggressive Wealth Portfolio", "50% Growth Stocks, 20% Crypto, 20% Mid-cap Funds, 10% International ETFs").

% Final recommendation query (Returns Risk level, Title, and Strategy)
recommend(Age, Income, Goal, Risk, Title, Strategy) :-
    risk_profile(Risk, Age, Income, Goal),
    strategy(Risk, Title, Strategy).