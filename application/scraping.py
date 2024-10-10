import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from slugify import slugify
from thefuzz import process


def extract_links_from_page(url, plan, reference_data):
    response = requests.get(url, verify=False)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a", href=True)
    document_links = []
    for link in links:
        href = link["href"]
        document_url = urljoin(url, href)  # ensure urls are absolute
        if any(x in href.lower() for x in ["pdf", "doc", "document", "file"]):
            name = link.get_text(strip=True)
            name = clean_text(name)
            match = process.extractOne(name, reference_data)
            if match[1] > 85:
                document_type = match[0]
            else:
                document_type = None

            document_links.append(
                {
                    "name": name,
                    "reference": slugify(name),
                    "local_plan": plan.reference,
                    "document_url": document_url,
                    "documentation_url": url,
                    "document_type": document_type,
                }
            )
    return document_links


def clean_text(text):
    text = re.sub(
        r"[^\x00-\x7F]+", "'", text
    )  # replace all non-ASCII characters with an apostrophe
    text = re.sub(r"\[\s*pdf\s*\]", "", text, flags=re.IGNORECASE)  # remove [pdf] tags
    text = re.sub(r"\s+", " ", text)  # normalize any excessive spaces
    text = re.sub(
        r"\(\d+(,\d{3})?KB\)|\d+(,\d{3})?KB|\d+MB", "", text
    )  # remove file sizes like (63KB), 63KB, or 12MB
    words = text.split()
    cleaned_words = [
        word.rstrip("'") for word in words
    ]  # remove apostrophe at the end of each word
    cleaned_text = " ".join(cleaned_words)
    return cleaned_text.strip()
