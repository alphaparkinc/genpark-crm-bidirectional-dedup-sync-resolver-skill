import json
from client import CRMBidirectionalDedupResolver

def main():
    resolver = CRMBidirectionalDedupResolver()
    crm_db = [
        {
            "id": "CRM-1001",
            "email": "sarah.connor@cyberdyne.com",
            "company_name": "Cyberdyne Systems Inc.",
            "source": "salesforce_master",
            "title": "Director of Security",
            "phone": "+1-555-0199"
        }
    ]
    incoming = {
        "email": "sarah.connor@cyberdyne.com",
        "company_name": "Cyberdyne Systems",
        "source": "direct_user_form",
        "title": "VP of Security",
        "linkedin_url": "https://linkedin.com/in/sconnor"
    }
    sync_result = resolver.deduplicate_and_sync(incoming, crm_db)
    print("CRM Deduplication & Sync Result:")
    print(json.dumps(sync_result, indent=2))
    assert sync_result["action"] == "MERGE_UPDATE"
    assert sync_result["matched_record_id"] == "CRM-1001"
    print("CRM dedup resolver verification complete: PASS")

if __name__ == "__main__":
    main()
