"""Small deterministic decisions and runtime validation, independently testable."""
from datetime import date, time
import re
from agent.tools import ORDERS

CLAIMS = 'parcelpigeon.example/claims'
FALLBACK = 'I cannot confirm an answer from the available information. Please contact help@parcelpigeon.example.'


def refund_decision(order, *, working_days_late=None, arrival_time=None):
    service = order.get('service')
    expected, delivered = order.get('expected_delivery'), order.get('delivered')
    if not expected or not delivered:
        return {'outcome':'needs_information','missing':['delivery evidence']}
    expected, delivered = date.fromisoformat(expected), date.fromisoformat(delivered)
    if delivered < expected:
        eligible = False
    elif service == 'Same Day' and delivered == expected:
        if arrival_time is None:
            return {'outcome':'needs_information','missing':['arrival_time']}
        eligible = time.fromisoformat(arrival_time) > time(21)
    elif service == 'Same Day':
        eligible = True
    elif service == 'Next Day':
        eligible = delivered > expected
    elif service == 'Standard':
        if delivered == expected:
            eligible = False
        elif working_days_late is None:
            return {'outcome':'needs_information','missing':['approved working-day calculation']}
        else:
            if type(working_days_late) is not int or working_days_late < 0:
                raise ValueError('Invalid trusted working-day evidence')
            eligible = working_days_late > 2
    else:
        return {'outcome':'unsupported_rule'}
    return {'outcome':'eligible_to_claim' if eligible else 'ineligible','policy_id':'refunds','action_performed':False}


def validate_answer(answer, *, evidence, decision=None):
    failures = []
    if not answer.strip():
        failures.append('empty_answer')
    for order in ORDERS.values():
        for key in ['customer_name','address']:
            value = order.get(key,'')
            fragments = [value] + ([value.split(',')[-1].strip()] if key == 'address' else [])
            if any(v and v.casefold() in answer.casefold() for v in fragments):
                failures.append('personal_data')
    if re.search(r"\b(?:I(?:'ve| have)?|we(?:'ve| have)?)\s+(?:issued|processed|approved|sent|changed|cancelled|refunded)\b", answer, re.I):
        failures.append('unsupported_action_claim')
    if decision and decision.get('outcome') == 'eligible_to_claim' and CLAIMS not in answer:
        failures.append('missing_claim_route')
    # Exact numeric claims must occur in the approved evidence. This is a bounded
    # guard, not a proof that every possible natural-language claim is grounded.
    approved = str(evidence)
    for number in re.findall(r'(?<![A-Za-z])\d+(?:\.\d+)?', answer):
        if number not in approved:
            failures.append('unsupported_number')
            break
    return sorted(set(failures))
