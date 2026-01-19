"""
Helper functions for data processing and manipulation.
"""
from collections import defaultdict


def group_results_by_district(results):
    """Group scraping results by district for display."""
    districts_data = defaultdict(lambda: {'companionships': defaultdict(list)})

    for row in results:
        district_name = row['district']
        interviewer = row['interviewer']
        comp_id = row['companionship_id']
        districts_data[district_name]['interviewer'] = interviewer
        districts_data[district_name]['companionships'][comp_id].append({
            'name': row['name'],
            'phone': row['phone'],
            'email': row['email']
        })

    scraped_districts = []
    for district_name, data in districts_data.items():
        companionships = []
        for comp_id, members in data['companionships'].items():
            companionships.append({
                'companionship_id': comp_id,
                'members': members
            })
        scraped_districts.append({
            'name': district_name,
            'interviewer': data['interviewer'],
            'companionships': companionships
        })

    return scraped_districts
