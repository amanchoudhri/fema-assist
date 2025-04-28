import argparse
import requests

from datetime import datetime
from io import BytesIO

from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

def parse_media_item(item):
    """
    Parse a single media item to extract report information.
    
    Args:
        item: The BeautifulSoup item representing a media collection view
    
    Returns:
        dict or None: Report information dictionary if parsing succeeds, None otherwise
    """
    # Find the grid-item container
    grid_item = item.find("div", class_="grid-item")
    if not grid_item:
        return None
    
    # Extract the title
    title_elem = grid_item.find("h3")
    if not title_elem:
        return None
    
    title = title_elem.text.strip()
    
    # Extract the description
    desc_elem = grid_item.find("p")
    description = desc_elem.text.strip() if desc_elem else "No description available"
    
    # Extract the date
    date_elem = grid_item.find("time")
    date_str = date_elem.text.strip() if date_elem else "No date available"
    date_obj = None
    
    try:
        if date_elem and 'datetime' in date_elem.attrs:
            date_obj = datetime.strptime(date_elem['datetime'], "%Y-%m-%dT%H:%M:%SZ")
        elif date_str != "No date available":
            date_obj = datetime.strptime(date_str, "%B %d, %Y")
    except ValueError:
        # If date parsing fails, continue with the string version
        pass
    
    # Extract the document link
    link_elem = grid_item.find("a", href=True)
    link = link_elem["href"] if link_elem else None
    
    report_info = {
        "title": title,
        "description": description,
        "date": date_str,
        "datetime": date_obj,
        "link": link,
        "full_url": f"https://www.fema.gov{link}" if link and link.startswith("/") else link
    }
    
    return report_info


def parse_page(soup):
    # Find all report items - based on the FEMA website structure
    report_items = soup.find_all("div", class_="media-collection-view")
    
    if not report_items:
        print("No reports found. Try a different search term.")
        return []
    
    reports = []
    
    # Process each report
    for item in report_items:
        report_info = parse_media_item(item)
        if report_info:
            reports.append(report_info)

    return reports

def _search_fema_pda_reports(search_term, page=0):
    base_url = "https://www.fema.gov/disaster/how-declared/preliminary-damage-assessments/reports"

    params = {
        "combine": search_term,
        "page": page
    }

    # Make the request to the FEMA website
    response = requests.get(base_url, params=params)
    
    if response.status_code != 200:
        print(f"Error: Unable to connect to FEMA website. Status code: {response.status_code}")

    return response

def search_fema_pda_reports(state=None, year=None, disaster_num=None):
    """
    Search for Preliminary Damage Assessment reports for a specific state,
    disaster number, and year.
    
    Args:
        state (str, optional): The state name to search for. Defaults to None.
        year (int, optional): The year to filter by. Defaults to None (no filter).
        disaster_num (str, optional): The disaster number to search for. Defaults to None.
    
    Returns:
        list: A list of dictionaries containing report information
    """
    # Set up the search parameters - FEMA uses the 'combine' parameter for search
    if disaster_num:
        search_term = disaster_num.strip()
        print(f"Searching for Preliminary Damage Assessment reports for disaster ID: {disaster_num}...")
    elif state:
        search_term = state.strip()
        print(f"Searching for Preliminary Damage Assessment reports for state: {state}...")
    else:
        print("No search criteria provided. Please specify either a state or disaster number.")
        return []
    
    response = _search_fema_pda_reports(search_term)
    soup = BeautifulSoup(response.text, 'html.parser')

    reports = parse_page(soup)

    # check for multiple pages
    n_pages = count_result_pages(soup)

    if n_pages > 1:
        for page in range(1, n_pages):
            response = _search_fema_pda_reports(search_term, page=page)
            soup = BeautifulSoup(response.text, 'html.parser')
            reports.extend(parse_page(soup))

    if year:
        reports = list(filter(lambda x: x['datetime'].year == int(year), reports))

    return reports

def count_result_pages(soup):
    """Check if there are more pages of results."""
    pagination = soup.find("nav", class_="pager")
    if pagination:
        pages = pagination.find_all("li", class_="pager__item")
        return len(pages)
    return 1

def format_reports(reports):
    """Format the reports for display"""
    if not reports:
        return "No matching reports found."
    
    result = f"Found {len(reports)} matching report(s):\n\n"
    
    for i, report in enumerate(reports, 1):
        result += f"Report {i}:\n"
        result += f"Title: {report['title']}\n"
        result += f"Date: {report['date']}\n"
        result += f"Description: {report['description']}\n"
        
        if report['link']:
            result += f"Download Link: {report['full_url']}\n"
        
        result += "\n" + "-" * 50 + "\n"
    
    return result

def extract_text(pdf_content):
    pdf = PdfReader(BytesIO(pdf_content))
    text = []
    for page in pdf.pages:
        text.append(page.extract_text())

    return '\n'.join(text)

def fetch_report_details(url):
    """Fetch additional details about a report by downloading the PDF."""
    # This function could be expanded to extract more information from the PDFs
    # For now, it's a placeholder for future enhancement
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            text = extract_text(response.content).strip()
            return text
    except Exception as e:
        print(f"Error fetching report: {e}")

def main():
    parser = argparse.ArgumentParser(description='Search for FEMA Preliminary Damage Assessment Reports')
    parser.add_argument('--state', help='The state name to search for')
    parser.add_argument('--disaster-num', help='The disaster number to search for (e.g., 4860)')
    parser.add_argument('--year', type=int, help='Filter reports by year')
    parser.add_argument('--download', action='store_true', help='Download the report PDFs')
    
    args = parser.parse_args()
    
    if not args.state and not args.disaster_num:
        print("Error: You must specify either --state or --disaster-num")
        parser.print_help()
        return
    
    disaster_num = getattr(args, 'disaster_num', None)
    reports = search_fema_pda_reports(args.state, args.year, disaster_num)
    print(format_reports(reports))

    for report in reports:
        details = fetch_report_details(report['full_url'])
        if details:
            print(details[:100] + '...')

    if args.download and reports:
        print("Downloading reports is not implemented in this version.")

if __name__ == "__main__":
    main()
