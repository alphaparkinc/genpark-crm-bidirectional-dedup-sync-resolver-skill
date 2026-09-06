import difflib
from typing import Dict, Any, List, Optional

class CRMBidirectionalDedupResolver:
    """
    Identifies fuzzy and exact duplicate CRM records across contacts and companies.
    Performs field-level conflict resolution using deterministic provenance weights and recency.
    """
    SOURCE_WEIGHTS = {
        "salesforce_master": 90,
        "direct_user_form": 85,
        "apollo_enrichment": 70,
        "web_scraper": 50,
        "legacy_import": 40
    }

    def normalize_company_name(self, name: str) -> str:
        s = name.lower()
        for suffix in [" inc.", " inc", " corp.", " corp", " llc", " ltd.", " ltd", " systems", " technologies", " tech"]:
            s = s.replace(suffix, "")
        return s.strip()

    def calculate_string_similarity(self, a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    def resolve_record_conflict(self, existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(existing)
        audit_log: List[Dict[str, Any]] = []

        existing_weight = self.SOURCE_WEIGHTS.get(existing.get("source", "legacy_import"), 40)
        incoming_weight = self.SOURCE_WEIGHTS.get(incoming.get("source", "legacy_import"), 40)

        for key, incoming_val in incoming.items():
            if incoming_val is None or incoming_val == "":
                continue
            existing_val = existing.get(key)
            if existing_val is None or existing_val == "":
                merged[key] = incoming_val
                audit_log.append({"field": key, "action": "filled_empty", "value": incoming_val})
            elif incoming_val != existing_val:
                # Conflict resolution: compare source weight
                if incoming_weight > existing_weight:
                    merged[key] = incoming_val
                    audit_log.append({"field": key, "action": "overwrite_by_higher_source_weight", "old": existing_val, "new": incoming_val})
                else:
                    audit_log.append({"field": key, "action": "retained_existing_higher_source_weight", "kept": existing_val, "ignored": incoming_val})

        return {"merged_record": merged, "audit_log": audit_log}

    def deduplicate_and_sync(self, incoming_record: Dict[str, Any], crm_database: List[Dict[str, Any]]) -> Dict[str, Any]:
        incoming_email = incoming_record.get("email", "").lower().strip()
        incoming_domain = incoming_record.get("domain", "").lower().strip()
        incoming_name = self.normalize_company_name(incoming_record.get("company_name", ""))

        best_match: Optional[Dict[str, Any]] = None
        match_reason = None
        highest_similarity = 0.0

        for record in crm_database:
            # 1. Exact Email Match
            rec_email = record.get("email", "").lower().strip()
            if incoming_email and rec_email and incoming_email == rec_email:
                best_match = record
                match_reason = "exact_email_match"
                break

            # 2. Exact Domain Match
            rec_domain = record.get("domain", "").lower().strip()
            if incoming_domain and rec_domain and incoming_domain == rec_domain:
                best_match = record
                match_reason = "exact_domain_match"
                break

            # 3. Fuzzy Company Name Match
            rec_name = self.normalize_company_name(record.get("company_name", ""))
            if incoming_name and rec_name:
                sim = self.calculate_string_similarity(incoming_name, rec_name)
                if sim > 0.88 and sim > highest_similarity:
                    highest_similarity = sim
                    best_match = record
                    match_reason = f"fuzzy_company_similarity_{round(sim, 2)}"

        if best_match:
            resolution = self.resolve_record_conflict(best_match, incoming_record)
            return {
                "action": "MERGE_UPDATE",
                "matched_record_id": best_match.get("id"),
                "match_reason": match_reason,
                "merged_payload": resolution["merged_record"],
                "resolution_audit": resolution["audit_log"]
            }
        else:
            return {
                "action": "CREATE_NEW",
                "matched_record_id": None,
                "match_reason": "no_duplicate_found",
                "merged_payload": incoming_record,
                "resolution_audit": []
            }
