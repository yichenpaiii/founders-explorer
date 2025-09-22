from keybert import KeyBERT

def extract_keywords_from_text(text):
    # Initialize the KeyBERT model (defaults to 'all-MiniLM-L6-v2')
    kw_model = KeyBERT()

    # Extract keywords or keyphrases
    keywords = kw_model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 2),  # allow unigrams and bigrams
        stop_words='english',          # filter out English stop words
        nr_candidates=100,             # consider many more candidate phrases first
        top_n=20,                      # return many more keywords
        use_mmr=False,                 # do not prune similar/low-score phrases via MMR
        use_maxsum=False               # do not prune via MaxSum
    )
    return keywords

if __name__ == "__main__":
    text = """Summary

This course provides the foundations of sustainable management and finance : reviewed concepts include market failures and externalities, CSR, green finance, ESG, climate risk pricing. Includes case studies, policy tools, and corporate strategies for sustainability and climate adaptation.

Content


Session 1 Foundations of the Mixed Economic System
 
* The Invisible Hand and the Welfare Theorems
* Liberalism and Competition
* Planetary Boundaries: A Major Economic Challenge
* Missing Markets and Externalities
* The Tragedy of the Commons
* GDP vs. GrDP
* Alternative Public Levers to Improve System Performance and Associated Challenges
 
Session 2  The Firm and Sustainable Management
 
* Shareholder Value Maximization vs. Corporate Social Responsibility (CSR)
* The Benefit Corporation Movement
* Diversity, Equity, and Inclusion (DEI)
* Public-Private Partnerships (PPP) in Regulation
* Environmental Backlash
* Key Reports and Perspectives:
* The Draghi Report
* IMD Competitiveness Report
 

Session 3 Sustainable Finance & Asset Pricing
 
* Introduction to Asset Pricing
* Markowitz Portfolio Theory and the CAPM
* Integrating Climate Risks into Asset Pricing Models
* Market Equilibrium and the Cost of Capital Channel
* Divestment Strategies and Sustainability Impacts
 
Session 4 Sustainable Finance & Corporate Finance
 
* Introduction to Capital Structure: Debt vs. Equity
* Sustainable Equity Investment:
* Shareholder Activism
* CEO Compensation and ESG Alignment
* ESG Integration in Corporate Strategy
* Sustainable Debt Instruments:
* Green Bonds
* Sustainability-Linked Bonds
* Innovative Financing Frameworks
* Greenwashing: Challenges and Detection
 
Session 5 Management: Selected Sustainability Topics
 
* Growth vs. De-growth
* Resource Scarcity and Strategic Responses
* Rising Inequality
* The Circular Economy Objective
* Managing Natural Capital
* Case Studies: Corporate Sustainability Strategies (e.g., Holcim, Nestlé, LO)
* The Emission Trading System
* Externalities in Innovation and Industrial Policy
* Poster Topics and Group Discussions
 
Session 6 Sustainable Finance: Advanced Topics & Poster Projects
 
* Carbon Offset Technologies:
* CCUS vs. Nature-Based Solutions (Benefits & Risks)
* Financing Green Innovation
* Climate Adaptation vs. Mitigation
* The Role of Insurance Markets in Sustainability"""

    if not text:
        print("Please provide text to extract keywords from.")
    else:
        results = extract_keywords_from_text(text)
        print("Extracted Keywords:")
        for kw, score in results:
            print(f"  {kw} (score: {score:.4f})")
