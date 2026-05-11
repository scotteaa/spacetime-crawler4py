import re
from urllib.parse import urlparse, urldefrag, urljoin, urlunparse
import utils.response
from bs4 import BeautifulSoup
from collections import Counter

# Global variables store report information about crawler
word_counts = Counter()
longest_page = ("", 0)
subdomains = {}
unique_pages = set()


allowed_domains = [
    ".ics.uci.edu",
    ".cs.uci.edu",
    ".informatics.uci.edu",
    ".stat.uci.edu",
]
blocked_domains = [
    "wics.ics.uci.edu",
    "grape.ics.uci.edu"
]


# English stopwords were sourced from https://www.ranks.nl/stopwords
stopwords = {"a", "about", "above", "after", "again", "against", "all", "am",
             "an", "and", "any", "are", "aren", "t", "as", "at", "be", "because",
             "been","before", "being", "below", "between", "both", "but", "by",
             "can", "cannot", "could", "couldn", "did", "didn", "do", "does",
             "doesn", "doing", "don", "down", "during", "each", "few", "for", "from",
             "further", "had", "hadn", "has", "hasn", "have", "having", "he", "d",
             "ll", "s", "her", "here", "hers", "herself", "him", "himself", "his",
             "how", "i", "m", "ve", "if", "in", "into", "is", "isn", "it", "its",
             "itself", "let", "me", "more", "most", "mustn", "my", "myself", "no", "nor",
             "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
             "ours", "ourselves", "out", "over", "own", "same", "shan", "she", "should",
             "shouldn", "so", "some", "such", "than", "that", "the", "their", "theirs",
             "them", "themselves", "then", "there", "these", "they", "re", "ve", "this",
             "those", "through", "to", "too", "under", "until", "up", "very", "was",
             "wasn", "we", "were", "weren", "what", "when", "where", "which", "while",
             "who", "whom", "why", "with", "won", "would", "wouldn", "you", "your",
             "yours", "yourself", "yourselves"}


def scraper(url: str, resp: utils.response.Response) -> list:
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    global longest_page
    hyperlinks = set()

    # First checks that the response is valid and contains content
    if resp.status != 200 or not resp.raw_response or not resp.raw_response.content:
        return list()

    # Ensures that the content is an html webpage
    content_type = resp.raw_response.headers.get('Content-Type', '')
    if 'text/html' not in content_type:
        return list()

    # Checks that pages aren't overly long (10 MB cutoff)
    content_length = resp.raw_response.headers.get('Content-Length')
    if content_length and int(content_length) > 10000000: # 10 MB in bytes
        return list()

    # Uses beautifulsoup to easily obtain content from html page
    soup = BeautifulSoup(resp.raw_response.content, 'lxml')
    # Links are organized under an <a> tag
    for tag in soup.find_all("a"):
        href = tag.get("href")
        if not href:
            continue

        # Constructs the complete url, disregarding queries/fragments
        full_url = urljoin(url, href)
        parsed = urlparse(full_url)
        final_url = urlunparse(parsed._replace(query="", fragment=""))

        # Adds to list of urls found on the webpage
        hyperlinks.add(final_url)

    # Regex pattern creates tokens out of webpage contents
    tokens = re.findall(r'[a-zA-Z0-9]+', soup.get_text().lower())

    # Checks whether the webpage has enough content
    word_count = len(tokens)
    if word_count < 50:
        return list(hyperlinks)

    # Compares the current webpage against the longest recorded page
    if word_count > longest_page[1]:
        longest_page = (url, word_count)

    # Updates word counts after removing stopwords/letters from page tokens
    filtered = [t for t in tokens if t not in stopwords and len(t) > 1]
    word_counts.update(filtered)

    # Creates a set for each unique subdomain to store its pages in
    hostname = urlparse(url).hostname
    if hostname not in subdomains:
        subdomains[hostname] = set()
    subdomains[hostname].add(url)

    # Adds current url to the total set of pages
    unique_pages.add(url)

    return list(hyperlinks)

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.

    # Extremely long urls could indicate a trap
    if len(url) > 200:
        return False

    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False

        # Too many queries could also indicate a trap
        if len(parsed.query.split('&')) > 5:
            return False

        # Any pages with calendar/event notation (inf loops) should be disregarded
        if (re.search(r'/\d{4}/\d{2}/', parsed.path) or
            re.search(r'\d{4}-\d{2}-\d{2}', parsed.path) or
            'calendar' in parsed.path.lower() or
            'events' in parsed.path.lower()):
            return False

        # Makes sure the domain is allowed before validating
        if not any(parsed.hostname.endswith(d) for d in allowed_domains):
            return False
        if any(parsed.hostname == d for d in blocked_domains):
            return False

        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise

def crawler_report():
    with open("report.txt", "w") as f:
        f.write(f"Unique pages: {len(unique_pages)}\n")
        f.write(f"Longest page: {longest_page[0]}, {longest_page[1]}\n")
        f.write("50 most common words:\n")
        for word, count in word_counts.most_common(50):
            f.write(f"{word}: {count}\n")
        f.write(f"Subdomains: {len(subdomains)}\n")
        for subdomain in sorted(subdomains.keys()):
            f.write(f"{subdomain}, {len(subdomains[subdomain])}\n")
