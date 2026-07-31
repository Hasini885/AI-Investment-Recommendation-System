% ============================================================================
%  SmartWealth - Expert System Risk Inference Rules
% ============================================================================
%
%  This file is the ONLY place where risk *inference* lives on the Prolog
%  side.  It deliberately does NOT know about portfolio titles or asset
%  allocations - those live in exactly one place (advisor.py: STRATEGIES) so
%  the two can never drift apart.
%
%  Model: risk capacity vs. risk tolerance.
%
%    1. CAPACITY  - what the user can objectively afford to risk, scored from
%                   age, income and goal.
%    2. CAPS      - hard constraints that override the score downwards
%                   (capital-preservation goal, no investable surplus,
%                   nearing retirement, advanced age).
%    3. TOLERANCE - what the user says they are comfortable with.
%                   Final level = min(capacity, tolerance).  Standard
%                   financial-planning practice: never exceed either one.
%    4. SENTIMENT - live market mood.  It can only ever tilt the result
%                   DOWN (defensive) - never up.  The market may make us
%                   more cautious; it must not make us braver than the
%                   user's own capacity or stated comfort.
%
%  Every clause below is deterministic (cuts on the guarded clauses, ordered
%  fall-through) so `recommend/7` has exactly one solution for any input.
%  advisor.py mirrors this logic line for line, and test_advisor.py asserts
%  the two engines agree across the whole input grid.
% ============================================================================

% ---------------------------------------------------------------------------
% Level encoding: 1 = low, 2 = medium, 3 = high
% ---------------------------------------------------------------------------
level_name(1, low).
level_name(2, medium).
level_name(3, high).

% ---------------------------------------------------------------------------
% Component scores
% ---------------------------------------------------------------------------

% Longer investment horizon -> more capacity to ride out volatility.
age_score(Age, 3) :- Age =< 30, !.
age_score(Age, 2) :- Age =< 45, !.
age_score(Age, 1) :- Age =< 60, !.
age_score(_,   0).

% Monthly investable income in INR.  More surplus -> more capacity.
income_score(Income, 3) :- Income >= 75000, !.
income_score(Income, 2) :- Income >= 40000, !.
income_score(Income, 1) :- Income >= 25000, !.
income_score(_,      0).

% The goal shapes how much volatility is acceptable on the way there.
goal_score(wealth,     2) :- !.
goal_score(education,  1) :- !.
goal_score(retirement, 1) :- !.
goal_score(safety,     0) :- !.
goal_score(_,          1).

% Self-declared risk tolerance.
tolerance_level(low,    1) :- !.
tolerance_level(medium, 2) :- !.
tolerance_level(high,   3) :- !.
tolerance_level(_,      2).

capacity_score(Age, Income, Goal, Score) :-
    age_score(Age, A),
    income_score(Income, I),
    goal_score(Goal, G),
    Score is A + I + G.

% Score is 0..8.  Split into three bands.
base_capacity(Age, Income, Goal, 3) :-
    capacity_score(Age, Income, Goal, S), S >= 6, !.
base_capacity(Age, Income, Goal, 2) :-
    capacity_score(Age, Income, Goal, S), S >= 3, !.
base_capacity(_, _, _, 1).

base_rule(3, capacity_high).
base_rule(2, capacity_medium).
base_rule(1, capacity_low).

% ---------------------------------------------------------------------------
% Hard caps -- cap_rule(RuleId, Age, Income, Goal, MaxLevel)
%
% Each states "whatever the score said, this profile may not exceed MaxLevel".
% They are checked independently; the tightest one wins.
% ---------------------------------------------------------------------------

% Capital preservation is the goal -- growth assets are inappropriate.
cap_rule(safety_goal_cap, _, _, safety, 1).

% Below a realistic investable surplus, the priority is an emergency fund,
% not market exposure.  (This is what makes a 22-year-old with no income
% conservative rather than "young therefore aggressive".)
cap_rule(insufficient_surplus, _, Income, _, 1) :-
    Income < 25000.

% Retirement inside ~5 years: sequence-of-returns risk dominates.
cap_rule(retirement_near_term, Age, _, retirement, 1) :-
    Age >= 55.

% Retirement on a 10-20 year horizon: moderate, not aggressive.
cap_rule(retirement_mid_term, Age, _, retirement, 2) :-
    Age >= 45, Age < 55.

% Past normal retirement age, capital preservation dominates regardless
% of the stated goal.
cap_rule(senior_cap, Age, _, _, 2) :-
    Age > 60.

% Apply every cap that actually binds (i.e. sits strictly below the base
% capacity).  Capped = the tightest limit; Fired = the rules at that limit.
applied_caps(Age, Income, Goal, Base, Capped, Fired) :-
    findall(Max-Id,
            ( cap_rule(Id, Age, Income, Goal, Max), Max < Base ),
            Pairs),
    (   Pairs == []
    ->  Capped = Base,
        Fired  = []
    ;   findall(M, member(M-_, Pairs), Maxes),
        min_list(Maxes, Capped),
        findall(Id, member(Capped-Id, Pairs), Fired)
    ).

% ---------------------------------------------------------------------------
% Tolerance and sentiment adjustments
% ---------------------------------------------------------------------------
apply_tolerance(Capped, TolLevel, TolLevel, [tolerance_limits]) :-
    TolLevel < Capped, !.
apply_tolerance(Capped, _, Capped, []).

apply_sentiment(negative, Level, Adjusted, [bearish_defensive]) :-
    Level > 1, !,
    Adjusted is Level - 1.
apply_sentiment(_, Level, Level, []).

% ---------------------------------------------------------------------------
% Entry point
%
%   recommend(+Age, +Income, +Tolerance, +Goal, +Sentiment, -Risk, -RuleString)
%
% RuleString is a comma-separated atom (e.g. 'capacity_high,tolerance_limits').
% It is returned as a single atom rather than a Prolog list purely because
% that marshals reliably across every pyswip version; advisor.py splits it.
% ---------------------------------------------------------------------------
recommend(Age, Income, Tolerance, Goal, Sentiment, Risk, RuleString) :-
    base_capacity(Age, Income, Goal, Base),
    base_rule(Base, BaseRule),
    applied_caps(Age, Income, Goal, Base, Capped, CapRules),
    tolerance_level(Tolerance, TolLevel),
    apply_tolerance(Capped, TolLevel, Combined, TolRules),
    apply_sentiment(Sentiment, Combined, Final, SentRules),
    level_name(Final, Risk),
    append([BaseRule], CapRules, R1),
    append(R1, TolRules, R2),
    append(R2, SentRules, Rules),
    atomic_list_concat(Rules, ',', RuleString).
