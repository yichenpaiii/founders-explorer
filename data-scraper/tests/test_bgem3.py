from FlagEmbedding import BGEM3FlagModel
import json

model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=False)

courses = [
    """Summary

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
* Case Studies: Corporate Sustainability Strategies (e.g., Holcim, NestlÃ©, LO)
* The Emission Trading System
* Externalities in Innovation and Industrial Policy
* Poster Topics and Group Discussions
 
Session 6 Sustainable Finance: Advanced Topics & Poster Projects
 
* Carbon Offset Technologies:
* CCUS vs. Nature-Based Solutions (Benefits & Risks)
* Financing Green Innovation
* Climate Adaptation vs. Mitigation
* The Role of Insurance Markets in Sustainability"""
]

# generate dense embedding
output = model.encode(
    courses,
    return_dense=True,
    return_sparse=False,
    return_colbert_vecs=False,
    max_length=8192,
)
v_doc = output['dense_vecs']

# Convert to plain Python lists to avoid NumPy's truncated display with '...'
try:
    v_list = getattr(v_doc, "tolist", lambda: v_doc)()
except Exception:
    v_list = v_doc

# Pretty-print full vectors as compact JSON
print("v_doc:", json.dumps(v_list, ensure_ascii=False, separators=(",", ":")))
