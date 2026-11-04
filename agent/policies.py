"""Versioned policy catalogue, hybrid index and deliberately small rule vocabulary."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

CATALOGUE = Path(__file__).parent / "data" / "policies.json"
INDEX = Path(__file__).parent.parent / ".cache" / "policy-index.json"


def runtime_policy(policy):
    """Keep development examples and gold outcomes out of all model evidence."""
    return {k: policy[k] for k in ('id', 'version', 'topic', 'text', 'aliases', 'rule', 'active', 'applicability') if k in policy}


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - {"a", "the", "i", "can", "send", "my", "is", "to", "it"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def load_policies(path=CATALOGUE):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    seen = set()
    for p in records:
        if not all(k in p for k in ("id", "version", "topic", "text", "aliases", "active", "tests")):
            raise ValueError("Policy missing required fields")
        if p["id"] in seen or not isinstance(p["version"], int) or p["version"] < 1:
            raise ValueError("Duplicate policy ID or invalid version")
        seen.add(p["id"])
        if not isinstance(p["active"], bool) or not isinstance(p["aliases"], list):
            raise ValueError("Invalid policy metadata")
        if not isinstance(p['text'],str) or not p['text'].strip() or any(not isinstance(a,str) or not a.strip() for a in p['aliases']):
            raise ValueError('Policy text/aliases must be nonempty strings')
        if not isinstance(p['tests'],list):
            raise ValueError('Policy tests must be an array')
        if p.get('rule'):
            rule=p['rule']
            if rule.get('outcome') != 'prohibited' or not isinstance(rule.get('required',[]),list):
                raise ValueError('Invalid initial rule vocabulary')
            if p['active'] and not p['tests']:
                raise ValueError('Executable policies need reviewed examples')
            for condition in rule.get('conditions',[]):
                if not all(k in condition for k in ['field','op','value']):
                    raise ValueError('Invalid rule condition')
                if condition['field'] not in rule.get('required',[]):
                    raise ValueError('Conditional facts must be required')
        for case in p["tests"]:
            if not all(k in case for k in ("query", "facts", "expected")):
                raise ValueError("Policy test missing query, facts or expected")
    return [p for p in records if p["active"]]


def build_index(records=None, path=INDEX, embed=None, model="lexical"):
    records = load_policies() if records is None else records
    path = Path(path)
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    cached = old.get("entries", {}) if old.get("model") == model else {}
    entries = {}
    for p in records:
        fingerprint = digest(p)
        previous = cached.get(p["id"], {})
        vector = previous.get("vector") if previous.get("hash") == fingerprint else None
        if embed and vector is None:
            vector = embed(p["text"] + " " + " ".join(p["aliases"]))
        entries[p["id"]] = {"hash": fingerprint, "vector": vector}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model": model, "entries": entries}), encoding="utf-8")
    return entries


def cosine(a, b):
    if len(a) != len(b):
        raise ValueError("Embedding dimensions changed; rebuild index")
    norm = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / norm if norm else 0


class PolicyStore:
    def __init__(self, records=None, embed=None, index=None):
        self.records = load_policies() if records is None else [p for p in records if p["active"]]
        self.embed, self.index = embed, index or {}

    def search(self, query, topic=None, limit=5):
        candidates = [p for p in self.records if topic is None or p["topic"] == topic]
        q = words(query)
        vector = self.embed(query) if self.embed else None
        ranked = []
        for p in candidates:
            terms = words(p["text"] + " " + " ".join(p["aliases"]))
            lexical = len(q & terms) / max(1, len(q))
            alias = any(re.search(r"\b" + re.escape(a.lower()) + r"\b", query.lower()) for a in p["aliases"])
            entry = self.index.get(p["id"], {})
            semantic = 0
            if vector is not None and entry.get("hash") == digest(p) and entry.get("vector"):
                semantic = max(0, cosine(vector, entry["vector"]))
            score = lexical + float(alias) + semantic
            if score > 0:
                ranked.append((score, p))
        return [p for _, p in sorted(ranked, key=lambda row: (-row[0], row[1]["id"]))[:limit]]

    def context(self, query, topics):
        # Mandatory small topic groups are included, not just whichever sections rank first.
        mandatory = [p for p in self.records if p["topic"] in topics and p["topic"] != "prohibited_items"]
        retrieved = self.search(query, "prohibited_items" if "prohibited_items" in topics else None)
        return list({p["id"]: p for p in mandatory + retrieved}.values())


def evaluate_policy(policy, facts):
    rule = policy.get("rule")
    if not rule:
        return {"outcome": "unsupported_rule", "policy_id": policy["id"]}
    required = rule.get("required", [])
    missing = [key for key in required if key not in facts]
    if missing:
        return {"outcome": "needs_information", "missing": missing, "policy_id": policy["id"]}
    comparisons = {"eq": lambda a,b: type(a) is type(b) and a == b,
                   "gt": lambda a,b: type(a) in (int,float) and a > b}
    for condition in rule.get("conditions", []):
        op = comparisons.get(condition["op"])
        if op is None:
            return {"outcome": "unsupported_rule", "policy_id": policy["id"]}
        value = facts.get(condition['field'])
        if (condition['op']=='gt' and type(value) not in (int,float)) or (condition['op']=='eq' and type(value) is not type(condition['value'])):
            return {'outcome':'needs_information','missing':[condition['field']], 'policy_id':policy['id']}
        if not op(facts.get(condition["field"]), condition["value"]):
            return {"outcome": "not_prohibited_by_rule", "policy_id": policy["id"]}
    return {"outcome": rule["outcome"], "policy_id": policy["id"]}


def explicit_facts(question):
    """Conservative extractors for the two initial conditional item rules."""
    facts = {}
    volume = re.findall(r'\b(\d+(?:\.\d+)?)\s*ml\b', question, re.I)
    if len(set(volume)) == 1:
        facts['volume_ml'] = float(volume[0])
    if re.search(r'\bnot standalone\b', question, re.I):
        facts['standalone'] = False
    elif re.search(r'\b(standalone|on (?:its|their) own)\b', question, re.I):
        facts['standalone'] = True
    elif re.search(r'\b(inside|installed|in a laptop)\b', question, re.I):
        facts['standalone'] = False
    return facts


def configured_store(index_path=INDEX):
    import os
    from agent.llm import client_for
    if not os.getenv("EMBEDDING_MODEL"):
        return PolicyStore()
    client, model = client_for("EMBEDDING")
    embed = lambda text: client.embeddings.create(model=model, input=text).data[0].embedding
    entries = build_index(embed=embed, model=model, path=index_path)
    store = PolicyStore(embed=embed, index=entries)
    store.embedding_model = model
    return store


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--semantic", action="store_true")
    args = parser.parse_args()
    if args.semantic:
        import os
        from agent.llm import load_dotenv
        load_dotenv()
        if not os.getenv("EMBEDDING_MODEL"):
            parser.error("Set EMBEDDING_MODEL before --semantic")
        store = configured_store()
    else:
        build_index()
    print(f"Validated/indexed {len(load_policies())} active policies. Index: {INDEX}")
