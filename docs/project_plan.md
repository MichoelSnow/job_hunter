# Job Search Application - Complete Project Plan

**Purpose**: Comprehensive technical specification for building an intelligent job search aggregation and tracking application

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Project Context & Goals](#project-context--goals)
3. [System Architecture](#system-architecture)
4. [Technical Stack](#technical-stack)
5. [Database Schema](#database-schema)
6. [Component Specifications](#component-specifications)
7. [Implementation Phases](#implementation-phases)
8. [API Integration Details](#api-integration-details)
9. [Machine Learning & Scoring](#machine-learning--scoring)
10. [User Interface Requirements](#user-interface-requirements)
11. [Configuration & Environment](#configuration--environment)
12. [Testing Strategy](#testing-strategy)
13. [Future Enhancements](#future-enhancements)

---

## Project Overview

### Project Name
**job_search**

### Executive Summary
A personalized job search automation tool designed to aggregate job listings from multiple sources, filter based on specific criteria (data leadership roles in healthcare/healthtech, in-office positions in Manhattan/Brooklyn), and provide intelligent matching scores between user qualifications and job requirements.

### Primary User
Single user (job seeker) looking for data leadership positions in healthcare/healthtech industry with specific location and work arrangement requirements.

### Key Differentiators
- Multi-source aggregation (APIs + custom scrapers)
- Intelligent two-way matching (user→job fit AND job→user fit)
- Focus on healthcare/healthtech industry
- Location-specific filtering (Manhattan/Brooklyn, in-office requirement)
- Cost-effective (operates on free/low-cost API tiers)

---

## Project Context & Goals

### Problem Statement
Job searching across multiple platforms is time-consuming and inefficient. The user currently spends excessive time:
- Manually checking multiple job boards and aggregators
- Visiting individual company career pages
- Filtering through remote-only positions (user wants in-office work)
- Evaluating job-candidate fit manually

### Solution
Build an automated system that:
1. **Discovers** relevant jobs from multiple sources
2. **Filters** based on hard criteria (location, work arrangement, role type)
3. **Scores** jobs on candidate-job fit (bidirectional)
4. **Tracks** application status and related information
5. **Presents** curated results in a clean, manageable interface

### Success Metrics
- Reduce time spent on job search by 70%+
- Discover 90%+ of relevant job postings in target market
- Provide accurate fit scores (±15% of manual assessment)
- Cost under $10/month to operate
- Weekly execution time under 10 minutes

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface (React)                   │
│  - Job Dashboard  - Application Tracker  - Settings         │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backend API (FastAPI)                 │
│  - Job Endpoints  - Scoring Engine  - Data Sync             │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                Database (PostgreSQL/DuckDB/SQLite)           │
│  - Jobs  - Companies  - User Profile  - Applications        │
└─────────────────────────────────────────────────────────────┘
                    ▲
                    │
    ┌───────────────┴───────────────┐
    │                               │
    ▼                               ▼
┌─────────────────┐         ┌──────────────────┐
│  Job Aggregator │         │ Custom Scrapers  │
│    (API Layer)  │         │   (for specific  │
│                 │         │  company sites)  │
│ - JSearch API   │         │                  │
│ - FlyByAPIs     │         │ - Target list    │
│ - Serply.io     │         │ - HTML parsing   │
└─────────────────┘         └──────────────────┘
```

### Data Flow

**Weekly Job Refresh Flow:**
```
1. Trigger job refresh (manual via UI or scheduled)
   ↓
2. Execute API queries for target criteria
   ↓
3. Execute custom scrapers for priority companies
   ↓
4. Deduplicate and normalize job data
   ↓
5. Parse job descriptions (NLP/text extraction)
   ↓
6. Calculate match scores (ML scoring engine)
   ↓
7. Store in database (upsert logic for existing jobs)
   ↓
8. Update UI with new/updated jobs
```

**User Interaction Flow:**
```
User views dashboard
   ↓
Filters/sorts jobs by score, date, company, etc.
   ↓
Clicks job to view details
   ↓
Updates application status, adds notes
   ↓
Backend updates database
   ↓
UI reflects changes
```

---

## Technical Stack

### Backend
- **Language**: Python 3.13+
- **Web Framework**: FastAPI
  - Built-in async support
  - Automatic API documentation (Swagger/OpenAPI)
  - Type hints and validation (Pydantic)
  - Better performance
- **Key Libraries**:
  - `requests` - HTTP client for API calls
  - `tenacity` - Retry logic for all external API calls
  - `beautifulsoup4` - HTML parsing for scrapers (fallback)
  - `lxml` - Fast XML/HTML parser
  - `scikit-learn` - TF-IDF vectorization and cosine similarity
  - `sentence-transformers` - Local semantic embeddings (Phase 2 scoring; no API cost)
  - `numpy` - Numerical operations
  - `pandas` - Data manipulation
  - `python-docx` / `pypdf` - Resume parsing
  - `spacy` - NLP/NER for text processing
  - `pydantic-settings` - Typed config loaded from `.env`
  - `sqlalchemy` - ORM for database operations

### Database
- **Primary Options** (choose one):
  - **PostgreSQL** - Robust, full-featured, good for eventual cloud deployment
  - **DuckDB** - Analytical database, excellent for data analysis, embedded
  - **SQLite** - Simplest, file-based, zero configuration
- **Recommendation**: Start with SQLite for simplicity, migrate to PostgreSQL if deploying to cloud

### Frontend
- **Framework**: React 18+
- **Build Tool**: Vite (fast, modern)
- **UI Library**: 
  - Tailwind CSS for styling
  - shadcn/ui or Material-UI for components
- **State Management**: 
  - React Query (for API state)
  - Zustand or Context API (for local state)
- **Key Libraries**:
  - `axios` - HTTP client
  - `react-router-dom` - Routing
  - `react-table` or `tanstack-table` - Data tables
  - `date-fns` - Date manipulation
  - `recharts` or `chart.js` - Visualizations (optional)

### DevOps & Tools
- **Version Control**: Git
- **Package Management**: 
  - Python: `poetry` (`pyproject.toml`)
  - Node: `pnpm`
- **API Testing**: Postman or Thunder Client
- **Code Quality**: 
  - `ruff` (Python linting and formatting — replaces black + pylint)
  - `eslint` (JavaScript linting)
  - `prettier` (JavaScript formatting)

### Deployment Options
- **Local Development**: 
  - Run backend and frontend locally
  - SQLite database
- **Future Cloud Options** (optional):
  - Backend: AWS Lambda, Google Cloud Run, or Heroku
  - Frontend: Vercel, Netlify, or AWS S3 + CloudFront
  - Database: AWS RDS (PostgreSQL) or Supabase

---

## Database Schema

### User Profile (config file, not a DB table)

User identity and skills are stored in `config/user_profile.yaml`, edited manually once at setup. The `text_parser` and `scoring_engine` load this file at startup. There is no `users` or `user_skills` table — this is a single-user tool with no auth layer. See [architecture.md](architecture.md) for the file format.

### Core Tables

#### 1. `user_criteria`
User's job search preferences and requirements.

```sql
CREATE TABLE user_criteria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    criterion_type VARCHAR(100) NOT NULL,  -- e.g., 'location', 'salary', 'title'
    criterion_value TEXT NOT NULL,
    is_hard_requirement BOOLEAN DEFAULT FALSE,  -- Hard vs soft criteria
    weight FLOAT DEFAULT 1.0,  -- For soft criteria scoring
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Example criteria rows:**
- `criterion_type='location'`, `criterion_value='Manhattan,Brooklyn'`, `is_hard_requirement=TRUE`
- `criterion_type='work_arrangement'`, `criterion_value='in_office_3_plus_days'`, `is_hard_requirement=TRUE`
- `criterion_type='min_salary'`, `criterion_value='150000'`, `is_hard_requirement=FALSE`, `weight=0.8`
- `criterion_type='industry'`, `criterion_value='healthcare,healthtech'`, `is_hard_requirement=FALSE`, `weight=1.0`

#### 2. `companies`
Companies in the job market.

```sql
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(255),  -- e.g., 'healthtech', 'healthcare'
    company_size VARCHAR(50),  -- e.g., 'small', 'medium', 'large', '50-200', '200-1000'
    funding_stage VARCHAR(100),  -- e.g., 'Series A', 'Series B', 'Public', 'Bootstrapped'
    headquarters_location VARCHAR(255),
    website_url VARCHAR(500),
    careers_page_url VARCHAR(500),
    logo_url VARCHAR(500),
    description TEXT,
    is_priority BOOLEAN DEFAULT FALSE,  -- High-priority companies to scrape
    scraper_enabled BOOLEAN DEFAULT FALSE,
    last_scraped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name)
);
```

#### 3. `jobs`
Job listings from all sources.

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id VARCHAR(255) UNIQUE,  -- ID from source (API or scraper)
    company_id INTEGER,
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(255),
    work_arrangement VARCHAR(100),  -- 'remote', 'hybrid', 'in_office', 'unknown'
    days_in_office INTEGER,  -- Number of days required in office
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency VARCHAR(10) DEFAULT 'USD',
    salary_period VARCHAR(50),  -- 'annual', 'hourly'
    employment_type VARCHAR(100),  -- 'full_time', 'part_time', 'contract'
    experience_level VARCHAR(100),  -- 'entry', 'mid', 'senior', 'lead', 'executive'
    posted_date DATE,
    discovered_date DATE NOT NULL,
    expiration_date DATE,
    application_url VARCHAR(1000) NOT NULL,
    source VARCHAR(100) NOT NULL,  -- 'jsearch_api', 'company_scraper', 'manual'
    source_url VARCHAR(1000),
    is_active BOOLEAN DEFAULT TRUE,
    match_score_user_to_job FLOAT,  -- How well user matches job (0-100)
    match_score_job_to_user FLOAT,  -- How well job matches user preferences (0-100)
    overall_match_score FLOAT,  -- Combined score
    score_calculated_at TIMESTAMP,
    raw_data JSON,  -- Store original API/scraper response
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
```

**Indexes:**
```sql
CREATE INDEX idx_jobs_company ON jobs(company_id);
CREATE INDEX idx_jobs_posted_date ON jobs(posted_date);
CREATE INDEX idx_jobs_match_score ON jobs(overall_match_score);
CREATE INDEX idx_jobs_is_active ON jobs(is_active);
CREATE INDEX idx_jobs_location ON jobs(location);
```

#### 4. `job_requirements`
Parsed requirements from job descriptions.

```sql
CREATE TABLE job_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    requirement_type VARCHAR(100),  -- 'skill', 'experience', 'education', 'certification'
    requirement_value VARCHAR(500),
    is_required BOOLEAN DEFAULT TRUE,  -- vs 'nice to have'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
```

#### 5. `applications`
User's application tracking.

```sql
CREATE TABLE applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    status VARCHAR(100) NOT NULL,  -- Flexible: user can define
    applied_date DATE,
    last_contact_date DATE,
    next_action_date DATE,
    referral_source VARCHAR(255),
    notes TEXT,
    cover_letter TEXT,
    resume_version VARCHAR(255),  -- Which version of resume was used
    metadata JSON,  -- Flexible field for any additional data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    UNIQUE(job_id)  -- One application per job
);
```

#### 6. `application_status_history`
Track status changes over time.

```sql
CREATE TABLE application_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    old_status VARCHAR(100),
    new_status VARCHAR(100) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
);
```

#### 7. `job_search_queries`
Track which queries have been run.

```sql
CREATE TABLE job_search_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text VARCHAR(500) NOT NULL,
    location VARCHAR(255),
    source VARCHAR(100) NOT NULL,  -- Which API/scraper
    results_count INTEGER,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);
```

#### 8. `api_usage_tracking`
Monitor API usage and costs.

```sql
CREATE TABLE api_usage_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name VARCHAR(100) NOT NULL,
    endpoint VARCHAR(255),
    request_count INTEGER DEFAULT 1,
    date DATE NOT NULL,
    cost_estimate FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Component Specifications

### Component 1: Job Discovery Engine

**Purpose**: Discover and fetch job listings from multiple sources.

**Sub-components**:

#### 1.1 API Aggregator Module
**File**: `backend/services/api_aggregator.py`

**Responsibilities**:
- Manage API credentials and rate limits
- Execute searches across multiple job APIs
- Handle retries and error handling
- Normalize responses into common format

**APIs to Integrate**:
1. **Primary**: JSearch API (via RapidAPI)
   - Free tier: Test/Basic plan
   - Endpoint: Job search with filters
   - Returns: Google for Jobs data
   
2. **Secondary**: FlyByAPIs Jobs Search
   - Free tier: 200 requests/month
   - Fallback/comparison source
   
3. **Tertiary**: Serply.io or SearchAPI.io
   - Additional coverage if needed

**Key Functions**:
```python
class JobAPIAggregator:
    def search_jobs(
        self,
        query: str,
        location: str,
        remote_filter: str = "on_site",
        date_posted: str = "week",
        employment_type: str = "FULLTIME"
    ) -> List[Dict]:
        """Search for jobs across all configured APIs."""
        pass
    
    def parse_api_response(self, raw_response: Dict, source: str) -> List[Job]:
        """Parse API response into normalized Job objects."""
        pass
    
    def deduplicate_jobs(self, jobs: List[Job]) -> List[Job]:
        """Remove duplicate jobs based on title, company, location."""
        pass
```

**Search Queries to Execute Weekly**:
- "data leader healthcare" + location
- "data director healthcare" + location
- "head of data healthcare" + location
- "VP data healthcare" + location
- "chief data officer healthcare" + location
- Similar queries with "healthtech" instead of "healthcare"

#### 1.2 Custom Scraper Framework
**Files**: `backend/app/services/scraper/`

**Source Priority** (use the first available for each company):
1. **Greenhouse boards JSON API** — `https://boards-api.greenhouse.io/v1/boards/{ats_id}/jobs` — structured JSON, no scraping
2. **Lever postings JSON API** — `https://api.lever.co/v0/postings/{ats_id}?mode=json` — structured JSON, no scraping
3. **HTML scraping** — `beautifulsoup4` + `lxml`, fallback only for companies with no public ATS API

The `companies.json` seed file includes an `ats_type` field (`"greenhouse"`, `"lever"`, `"custom"`) so the dispatcher knows which path to take without probing.

**Responsibilities**:
- Dispatch to the correct scraper based on `ats_type`
- Respect rate limits between requests
- Parse responses into normalized `Job` objects
- Fall back gracefully if an ATS API returns an unexpected structure

**Architecture**:
```python
class BaseJobScraper:
    """Base class for company-specific scrapers."""
    
    def __init__(self, company: Company):
        self.company = company
        self.session = requests.Session()
    
    def fetch_jobs(self) -> List[Job]:
        """Fetch all current job listings."""
        pass
    
    def parse_job(self, raw: dict) -> Job:
        """Parse a single job record into a normalized Job object."""
        pass

class GreenhouseJobsScraper(BaseJobScraper):
    """Fetches jobs via Greenhouse boards JSON API."""
    pass

class LeverJobsScraper(BaseJobScraper):
    """Fetches jobs via Lever postings JSON API."""
    pass

class HtmlJobScraper(BaseJobScraper):
    """HTML scraping fallback for custom career pages."""
    pass
```

#### 1.3 Company Discovery Helper
**File**: `backend/services/company_discovery.py`

**Purpose**: Help user build list of healthcare/healthtech companies to monitor.

**Approach** (Low technical burden):
1. Maintain a curated seed list of healthcare/healthtech companies (can be static JSON file)
2. Optionally: Use APIs like Crunchbase (limited free tier) or PitchBook to discover similar companies
3. User can manually add companies via UI

**Static Seed List** (examples):
```json
{
  "healthtech_companies": [
    {
      "name": "Oscar Health",
      "industry": "healthtech",
      "careers_url": "https://www.hioscar.com/careers"
    },
    {
      "name": "Flatiron Health",
      "industry": "healthtech",
      "careers_url": "https://flatiron.com/careers"
    },
    {
      "name": "Tempus",
      "industry": "healthtech",
      "careers_url": "https://www.tempus.com/careers/"
    }
  ]
}
```

**Enhancement** (optional, if time permits):
- Use Clearbit Company API (limited free tier) to enrich company data
- Search LinkedIn for companies with "healthcare" or "healthtech" in description
- User provides company names, system auto-fetches career page URL

### Component 2: Job Filtering Engine

**Purpose**: Apply hard criteria to filter out irrelevant jobs.

**File**: `backend/services/job_filter.py`

**Hard Filters**:
1. **Location Filter**:
   - Must include Manhattan or Brooklyn in location string
   - Reject jobs explicitly marked as "remote only"
   
2. **Work Arrangement Filter**:
   - Reject jobs marked as "fully remote"
   - Accept: in-office, hybrid, or unspecified
   - Preference for jobs mentioning 3+ days in office

3. **Role Level Filter**:
   - Must include leadership indicators: "lead", "director", "VP", "head of", "chief", "manager"
   - Reject junior/entry-level roles

**Implementation**:
```python
class JobFilter:
    def __init__(self, criteria: List[UserCriteria]):
        self.hard_criteria = [c for c in criteria if c.is_hard_requirement]
    
    def apply_hard_filters(self, jobs: List[Job]) -> List[Job]:
        """Apply all hard filters and return only matching jobs."""
        filtered = jobs
        for criterion in self.hard_criteria:
            filtered = self._apply_filter(filtered, criterion)
        return filtered
    
    def _apply_filter(self, jobs: List[Job], criterion: UserCriteria) -> List[Job]:
        """Apply a single filter criterion."""
        if criterion.criterion_type == 'location':
            return self._filter_by_location(jobs, criterion.criterion_value)
        elif criterion.criterion_type == 'work_arrangement':
            return self._filter_by_work_arrangement(jobs)
        # ... other filters
```

### Component 3: Resume & Job Description Parser

**Purpose**: Extract structured information from unstructured text.

**File**: `backend/services/text_parser.py`

**Responsibilities**:
1. Parse resume to extract:
   - Skills (technical, leadership, domain)
   - Years of experience
   - Job titles and companies
   - Education
   - Certifications

2. Parse job descriptions to extract:
   - Required skills
   - Preferred skills
   - Years of experience required
   - Education requirements
   - Certifications

**Tools**:
- **spaCy** with pre-trained models for NER (Named Entity Recognition)
- **Custom regex patterns** for skills extraction
- **Keyword matching** against skill taxonomy

**Implementation Approach**:
```python
class ResumeParser:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.skill_keywords = self._load_skill_taxonomy()
    
    def parse_resume(self, resume_text: str) -> Dict:
        """Extract structured data from resume text."""
        return {
            'skills': self._extract_skills(resume_text),
            'experience_years': self._calculate_experience(resume_text),
            'titles': self._extract_titles(resume_text),
            'education': self._extract_education(resume_text)
        }
    
    def _extract_skills(self, text: str) -> List[Dict]:
        """Extract skills using NER and keyword matching."""
        pass

class JobDescriptionParser:
    def parse_job_description(self, description: str) -> Dict:
        """Extract requirements from job description."""
        return {
            'required_skills': [],
            'preferred_skills': [],
            'experience_required': None,
            'education_required': []
        }
```

**Skill Taxonomy** (create static file):
```json
{
  "technical_skills": {
    "data_engineering": ["SQL", "Python", "Spark", "Airflow", "ETL", "data pipelines"],
    "data_science": ["machine learning", "statistics", "Python", "R", "TensorFlow"],
    "data_platforms": ["Snowflake", "Redshift", "BigQuery", "Databricks"],
    "visualization": ["Tableau", "Looker", "Power BI", "Metabase"]
  },
  "leadership_skills": [
    "team management",
    "stakeholder management",
    "strategy",
    "roadmap planning",
    "cross-functional collaboration"
  ],
  "domain_skills": {
    "healthcare": ["HIPAA", "HL7", "FHIR", "EHR", "clinical data", "healthcare analytics"],
    "healthtech": ["digital health", "telehealth", "health tech", "medical devices"]
  }
}
```

### Component 4: Scoring Engine

**Purpose**: Calculate bidirectional match scores between user and jobs.

**File**: `backend/services/scoring_engine.py`

**Scoring Dimensions**:

#### 4.1 User-to-Job Match Score (0-100%)
*"How well does the user match this job's requirements?"*

**Factors**:
1. **Skill Match** (50% weight):
   - Required skills present in user profile: +10 points each
   - Preferred skills present: +5 points each
   - Missing required skills: -10 points each
   
2. **Experience Match** (25% weight):
   - Years of experience meets requirement: +25 points
   - Exceeds requirement significantly: +15 points
   - Below requirement: 0 points
   
3. **Title/Level Match** (15% weight):
   - Current title aligns with job level: +15 points
   - Title is lower: -5 points
   
4. **Education Match** (10% weight):
   - Meets education requirement: +10 points

#### 4.2 Job-to-User Match Score (0-100%)
*"How well does this job match user's preferences?"*

**Factors** (soft criteria):
1. **Industry Match** (30% weight):
   - Healthcare/healthtech: +30 points
   - Adjacent industries: +15 points
   - Other: 0 points
   
2. **Salary Match** (25% weight):
   - Above user's minimum: +25 points
   - Salary not specified: +15 points (neutral)
   - Below minimum: 0 points
   
3. **Company Size Match** (15% weight):
   - Preferred size: +15 points
   - Acceptable range: +10 points
   - Outside preference: 0 points
   
4. **Funding Stage Match** (10% weight):
   - Preferred stage: +10 points
   - Other: +5 points
   
5. **Location Preference** (10% weight):
   - Preferred borough (Manhattan vs Brooklyn): +10 points
   - Other acceptable location: +5 points
   
6. **Work Arrangement** (10% weight):
   - Specifies 3+ days in office: +10 points
   - Hybrid (unspecified): +5 points

#### 4.3 Overall Match Score
```python
overall_score = (user_to_job_score * 0.6) + (job_to_user_score * 0.4)
```

**Implementation**:
```python
class ScoringEngine:
    def __init__(self, user_profile: User, user_criteria: List[UserCriteria]):
        self.user_profile = user_profile
        self.user_skills = self._load_user_skills()
        self.soft_criteria = [c for c in user_criteria if not c.is_hard_requirement]
    
    def calculate_match_scores(self, job: Job) -> Tuple[float, float, float]:
        """
        Returns: (user_to_job_score, job_to_user_score, overall_score)
        """
        user_to_job = self._calculate_user_to_job_score(job)
        job_to_user = self._calculate_job_to_user_score(job)
        overall = (user_to_job * 0.6) + (job_to_user * 0.4)
        
        return user_to_job, job_to_user, overall
    
    def _calculate_user_to_job_score(self, job: Job) -> float:
        """Calculate how well user matches job requirements."""
        score = 0.0
        
        # Skill matching using TF-IDF or simple overlap
        required_skills = self._get_job_required_skills(job)
        skill_overlap = len(set(self.user_skills) & set(required_skills))
        score += min(skill_overlap * 10, 50)  # Max 50 points
        
        # Experience matching
        # ... implementation
        
        return min(score, 100.0)
    
    def _calculate_job_to_user_score(self, job: Job) -> float:
        """Calculate how well job matches user preferences."""
        score = 0.0
        
        for criterion in self.soft_criteria:
            if self._job_meets_criterion(job, criterion):
                score += criterion.weight * 30  # Weighted scoring
        
        return min(score, 100.0)
```

**ML Enhancement** (Phase 2+):
- Use scikit-learn's `TfidfVectorizer` for semantic similarity
- Train a simple logistic regression model on user feedback
- Incorporate user's implicit feedback (which jobs they apply to)

### Component 5: Backend API

**Purpose**: Provide REST API for frontend to interact with data.

**File**: `backend/main.py` (FastAPI app) 

**Key Endpoints**:

#### Jobs
- `GET /api/jobs` - List all jobs with filters and pagination
- `GET /api/jobs/{job_id}` - Get single job details
- `POST /api/jobs/refresh` - Trigger job discovery process
- `PUT /api/jobs/{job_id}/score` - Recalculate scores for a job

#### Applications
- `GET /api/applications` - List user's applications
- `POST /api/applications` - Create new application
- `PUT /api/applications/{app_id}` - Update application status/notes
- `DELETE /api/applications/{app_id}` - Delete application

#### User Profile
- `GET /api/user/profile` - Get user profile
- `PUT /api/user/profile` - Update user profile
- `POST /api/user/resume` - Upload and parse resume
- `GET /api/user/skills` - Get user's skills
- `POST /api/user/skills` - Add/update skills

#### Companies
- `GET /api/companies` - List companies
- `POST /api/companies` - Add new company
- `PUT /api/companies/{company_id}` - Update company
- `GET /api/companies/{company_id}/jobs` - Get jobs from company

#### Criteria
- `GET /api/criteria` - Get user's criteria
- `POST /api/criteria` - Add new criterion
- `PUT /api/criteria/{criterion_id}` - Update criterion
- `DELETE /api/criteria/{criterion_id}` - Delete criterion

#### Analytics
- `GET /api/analytics/dashboard` - Dashboard statistics
- `GET /api/analytics/api-usage` - API usage tracking

**Example Endpoint Implementation (FastAPI)**:
```python
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

app = FastAPI(title="DataLeaderJobSearch API")

@app.get("/api/jobs", response_model=List[JobResponse])
async def get_jobs(
    skip: int = 0,
    limit: int = 50,
    min_score: float = 0,
    location: str = None,
    db: Session = Depends(get_db)
):
    """Get paginated list of jobs with optional filters."""
    query = db.query(Job).filter(Job.is_active == True)
    
    if min_score:
        query = query.filter(Job.overall_match_score >= min_score)
    
    if location:
        query = query.filter(Job.location.contains(location))
    
    jobs = query.order_by(Job.overall_match_score.desc())\
                .offset(skip)\
                .limit(limit)\
                .all()
    
    return jobs

@app.post("/api/jobs/refresh")
async def refresh_jobs(background_tasks: BackgroundTasks):
    """Trigger job discovery process in background."""
    background_tasks.add_task(run_job_discovery)
    return {"status": "Job discovery started"}
```

### Component 6: Frontend Dashboard

**Purpose**: User interface for viewing and managing jobs.

**Structure**:
```
frontend/
├── src/
│   ├── components/
│   │   ├── JobCard.jsx
│   │   ├── JobList.jsx
│   │   ├── JobDetails.jsx
│   │   ├── JobFilters.jsx
│   │   ├── ApplicationForm.jsx
│   │   ├── UserProfile.jsx
│   │   ├── CompanyList.jsx
│   │   └── Dashboard.jsx
│   ├── pages/
│   │   ├── HomePage.jsx
│   │   ├── JobsPage.jsx
│   │   ├── ApplicationsPage.jsx
│   │   ├── SettingsPage.jsx
│   │   └── CompaniesPage.jsx
│   ├── services/
│   │   ├── api.js
│   │   └── auth.js (if needed later)
│   ├── hooks/
│   │   ├── useJobs.js
│   │   └── useApplications.js
│   ├── App.jsx
│   └── main.jsx
```

**Key Pages**:

#### 6.1 Jobs Dashboard (`JobsPage.jsx`)
**Features**:
- Table/card view of jobs
- Sortable columns: match score, date posted, company, title
- Filterable by: score range, location, company, date posted
- Search by keywords
- Click job to view details in modal/side panel

**UI Elements**:
```jsx
<JobsPage>
  <JobFilters />
  <JobStats /> {/* Total jobs, avg score, etc. */}
  <JobList>
    {jobs.map(job => (
      <JobCard
        key={job.id}
        job={job}
        onApply={handleApply}
        onClick={() => setSelectedJob(job)}
      />
    ))}
  </JobList>
  {selectedJob && (
    <JobDetailsModal job={selectedJob} />
  )}
</JobsPage>
```

**JobCard Display**:
- Company name + logo
- Job title
- Location + work arrangement
- Match scores (user→job and job→user) with visual indicators
- Salary range (if available)
- Date posted
- Quick actions: "Apply", "View Details", "Hide"

#### 6.2 Job Details View
**Information Displayed**:
- Full job description
- Match score breakdown:
  - Skills match (which skills match, which are missing)
  - Experience match
  - Preference match
- Company information
- Application URL
- Application status (if applied)
- Notes section

#### 6.3 Applications Tracker (`ApplicationsPage.jsx`)
**Features**:
- Kanban board or table view
- Columns/statuses: "Not Applied", "Applied", "Phone Screen", "Interview", "Offer", "Rejected"
- Editable fields: status, notes, dates
- Upload cover letter
- Timeline of status changes

#### 6.4 Settings Page
**Sections**:
- User Profile (name, email, resume upload)
- Search Criteria (hard and soft criteria management)
- Company Management (add/remove companies to monitor)
- API Configuration (API keys, usage stats)

---

## Implementation Phases

See [implementation_checklist.md](implementation_checklist.md) for the full phase-by-phase task breakdown with completion status.

---

## API Integration Details

### JSearch API (Primary)

JSearch is provided by OpenWebNinja — a direct API, not via RapidAPI.

- **Docs**: https://www.openwebninja.com/api/jsearch/docs
- **Endpoint**: `https://api.openwebninja.com/jsearch/search`
- **Auth**: `x-api-key: JSEARCHAPI_KEY` header
- **Key parameter**: `query` (free-text, e.g. `"data director healthcare New York, NY"`)
- **Rate limits**: Check your OpenWebNinja dashboard; usage tracked in `api_usage_tracking` table
- **Implementation**: `backend/app/services/api_aggregator.py` — `JSearchClient`

### Serply (Secondary)

- **Docs**: https://serply.io/docs
- **Endpoint**: `https://api.serply.io/v1/job/search/`
- **Auth**: `X-Api-Key: SERPLYAPI_KEY` header
- **Key parameters**: `q` (query string), `num` (result count)
- **Implementation**: `backend/app/services/api_aggregator.py` — `SerplyClient`

Both clients use tenacity retry (3 attempts, exponential backoff) and gracefully skip if their API key is not configured.

---

## Machine Learning & Scoring

### Text Similarity Approach

**Using TF-IDF for skill matching**:
```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class SkillMatcher:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
    
    def calculate_skill_similarity(
        self,
        user_skills: List[str],
        job_requirements: List[str]
    ) -> float:
        """
        Calculate cosine similarity between user skills and job requirements.
        Returns: float between 0 and 1
        """
        # Combine into documents
        user_doc = ' '.join(user_skills)
        job_doc = ' '.join(job_requirements)
        
        # Vectorize
        tfidf_matrix = self.vectorizer.fit_transform([user_doc, job_doc])
        
        # Calculate similarity
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        
        return similarity
```

### Learning from User Behavior (Phase 2+)

Track which jobs user applies to and use this as positive signal:
```python
# When user applies to a job, record it
# Later, train a simple classifier

from sklearn.linear_model import LogisticRegression

def train_preference_model(applications: List[Application], jobs: List[Job]):
    """
    Train model to predict which jobs user is likely to apply to.
    Features: job attributes, scores, company info
    Target: applied (1) or not (0)
    """
    X = []  # Feature matrix
    y = []  # Labels
    
    for job in jobs:
        features = extract_features(job)
        X.append(features)
        y.append(1 if job.id in applied_job_ids else 0)
    
    model = LogisticRegression()
    model.fit(X, y)
    
    return model
```

---

## User Interface Requirements

### Design Principles
- **Clean and minimal**: Focus on content, reduce clutter
- **Information hierarchy**: Most important data (match scores) prominent
- **Fast filtering**: Quick filters for common criteria
- **Responsive**: Works on desktop and tablet (mobile optional)
- **Accessible**: Keyboard navigation, proper contrast

### Key UI Components

#### Job Card
```
┌─────────────────────────────────────────────┐
│ [Company Logo]  Company Name                │
│                                             │
│ Job Title                                   │
│ Location • Work Arrangement                 │
│                                             │
│ Match Score: ●●●●○ 85%                     │
│ ├─ You → Job: 90%                          │
│ └─ Job → You: 75%                          │
│                                             │
│ Salary: $150k-$200k                        │
│ Posted: 2 days ago                         │
│                                             │
│ [View Details]  [Apply]  [Hide]            │
└─────────────────────────────────────────────┘
```

#### Filters Panel
```
┌─────────────────┐
│ FILTERS         │
│                 │
│ Match Score     │
│ [====●====] 75% │
│                 │
│ Location        │
│ ☑ Manhattan     │
│ ☑ Brooklyn      │
│                 │
│ Posted          │
│ ○ 24 hours      │
│ ● Last week     │
│ ○ Last month    │
│                 │
│ Company         │
│ [Search...]     │
│                 │
│ [Reset Filters] │
└─────────────────┘
```

### Color Scheme Suggestions
- **High match (80-100%)**: Green (#10b981)
- **Medium match (60-79%)**: Yellow/Orange (#f59e0b)
- **Low match (0-59%)**: Gray (#6b7280)
- **Applied**: Blue (#3b82f6)

---

## Configuration & Environment

### Environment Variables

Only secrets and environment-specific values go in `.env`. Scoring weights, search queries, and other application logic stay in `settings.py`.

Create `.env` (copy from `.env.example`):
```bash
# Database
DATABASE_URL=sqlite:///./data/jobs.db

# API Keys
RAPIDAPI_KEY=your_rapidapi_key_here

# Application
DEBUG=True
CORS_ORIGINS=http://localhost:5173
```

### Configuration File

Create `backend/app/config/settings.py`. All scoring weights are defined here with defaults and injected into `ScoringEngine` at construction — never read from `.env` inside service classes.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./data/jobs.db"

    # API Keys
    rapidapi_key: str

    # Application
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]

    # Job Discovery
    max_jobs_per_query: int = 500
    api_request_delay_seconds: int = 1

    # Search Queries
    search_queries: list[str] = [
        "data director healthcare",
        "data leader healthcare",
        "head of data healthcare",
        "VP data healthcare",
        "chief data officer healthcare",
    ]

    search_locations: list[str] = [
        "New York, NY",
        "Manhattan, NY",
        "Brooklyn, NY",
    ]

    # Scoring weights — only defined here, injected into ScoringEngine
    user_to_job_weight: float = 0.6
    job_to_user_weight: float = 0.4
    skill_match_weight: float = 0.50
    experience_match_weight: float = 0.25
    title_match_weight: float = 0.15
    education_match_weight: float = 0.10

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
```

### User Criteria Configuration

User search criteria are stored in the `user_criteria` DB table and managed through the Settings UI. There is no parallel YAML file — the DB is the single source of truth. See [architecture.md](architecture.md) for the `user_profile.yaml` format (user identity and skills only).

---

## Testing Strategy

### Unit Tests

**Backend Tests** (`tests/test_*.py`):
```python
# tests/test_scoring_engine.py
def test_skill_matching():
    """Test that skill matching calculates correctly."""
    user_skills = ["Python", "SQL", "leadership"]
    job_requirements = ["Python", "SQL", "R"]
    
    score = calculate_skill_match(user_skills, job_requirements)
    
    assert score > 0.5  # Should have decent overlap

def test_hard_filters():
    """Test that hard filters exclude correctly."""
    jobs = [
        Job(location="San Francisco, CA"),
        Job(location="Manhattan, NY"),
        Job(location="Remote")
    ]
    
    filtered = apply_location_filter(jobs, ["Manhattan", "Brooklyn"])
    
    assert len(filtered) == 1
    assert filtered[0].location == "Manhattan, NY"
```

### Integration Tests

Test full workflow:
```python
def test_job_discovery_workflow():
    """Test complete job discovery and scoring."""
    # 1. Fetch jobs from API
    jobs = api_aggregator.search_jobs("data director", "New York")
    assert len(jobs) > 0
    
    # 2. Apply filters
    filtered = job_filter.apply_hard_filters(jobs)
    
    # 3. Calculate scores
    for job in filtered:
        scores = scoring_engine.calculate_match_scores(job)
        assert scores[2] >= 0 and scores[2] <= 100
    
    # 4. Save to database
    db.save_jobs(filtered)
```

### Frontend Tests

Use Jest and React Testing Library:
```javascript
// tests/JobCard.test.jsx
test('renders job card with correct data', () => {
  const job = {
    title: 'Data Director',
    company: { name: 'Health Corp' },
    overall_match_score: 85
  };
  
  render(<JobCard job={job} />);
  
  expect(screen.getByText('Data Director')).toBeInTheDocument();
  expect(screen.getByText('85%')).toBeInTheDocument();
});
```

### Manual Testing Checklist

- [ ] Job discovery fetches jobs successfully
- [ ] Jobs are filtered by location correctly
- [ ] Scores are calculated and reasonable
- [ ] Frontend displays jobs correctly
- [ ] Application status can be updated
- [ ] Resume can be uploaded and parsed
- [ ] Criteria can be modified
- [ ] API usage is tracked

---

## Future Enhancements

### Phase 2 Features
1. **Email Notifications**
   - Weekly digest of new high-match jobs
   - Alert when priority company posts new job
   
2. **Advanced Filtering**
   - Benefits filtering (health insurance, 401k, etc.)
   - Team size
   - Tech stack
   
3. **Batch Apply**
   - Generate customized cover letters using AI
   - One-click apply to multiple jobs
   
4. **Interview Prep**
   - Store interview questions
   - Track interview feedback
   - Company research notes

### Phase 3 Features
1. **Mobile App**
   - React Native or PWA
   - Push notifications
   
2. **Chrome Extension**
   - Save jobs from LinkedIn/Indeed directly
   - Auto-fill application forms
   
3. **Networking Integration**
   - LinkedIn connection suggestions
   - Identify mutual connections at companies
   
4. **Analytics Dashboard**
   - Application funnel metrics
   - Response rate by company/role type
   - Salary trends

### Scaling Considerations
1. **Multi-user Support**
   - Add authentication (JWT)
   - Separate user data
   - Billing/subscription management
   
2. **Cloud Deployment**
   - Deploy backend to AWS/GCP
   - Use managed PostgreSQL
   - Add caching (Redis)
   - CDN for frontend
   
3. **Advanced ML**
   - Deep learning for job-candidate matching
   - Company culture fit prediction
   - Salary prediction models

---

## Development Guidelines

### Code Style
- **Python**: Follow PEP 8, use `black` for formatting
- **JavaScript**: Use ESLint with Airbnb config, Prettier for formatting
- **Naming**: Use descriptive names, avoid abbreviations
- **Comments**: Document complex logic, not obvious code

### Git Workflow
- **Branches**: `main` (production), `develop` (integration), feature branches
- **Commits**: Use conventional commits (feat:, fix:, docs:, etc.)
- **PRs**: Self-review before merging

### Project Structure

See [architecture.md](architecture.md) for the full directory layout.

### Dependencies

All dependencies are managed at their latest stable versions. See `pyproject.toml` (backend, Poetry) and `frontend/package.json` (pnpm) for the authoritative list.

**Backend (`pyproject.toml` — managed by Poetry)**:
- `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `pydantic-settings`
- `requests`, `tenacity`
- `beautifulsoup4`, `lxml`
- `scikit-learn`, `numpy`, `pandas`
- `spacy`, `sentence-transformers`
- `python-multipart`, `python-docx`, `pypdf`, `pyyaml`

Dev: `pytest`, `pytest-asyncio`, `httpx`, `ruff`

**Frontend (`package.json` — managed by pnpm)**:
- `react`, `react-dom`, `react-router-dom`, `axios`
- `@tanstack/react-query`, `@tanstack/react-table`, `zustand`
- `date-fns`, `recharts`

Dev: `vite`, `@vitejs/plugin-react`, `tailwindcss`, `@tailwindcss/postcss`, `postcss`, `eslint`, `prettier`

---

## Quick Start

See [README.md](../README.md) for full setup and run instructions.

---

## Success Criteria

### MVP (Minimum Viable Product)
- [ ] Jobs fetched from at least one API source
- [ ] Jobs stored in database with deduplication
- [ ] Basic filtering by location and work arrangement
- [ ] Scoring algorithm calculating both dimensions
- [ ] Frontend displaying jobs with scores
- [ ] Application status tracking
- [ ] Resume uploaded and parsed

### Full V1.0
- [ ] Multiple API sources integrated
- [ ] Custom scrapers for 3+ priority companies
- [ ] Advanced filtering and search
- [ ] Polished UI with all features
- [ ] User can configure criteria
- [ ] Weekly automated job refresh
- [ ] Operating cost under $10/month

---

## Risk Mitigation

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limits exceeded | High | Monitor usage, implement caching, use multiple APIs |
| API costs higher than expected | Medium | Start with free tiers, track usage closely, set hard limits |
| Resume parsing inaccurate | Medium | Start simple (keyword matching), iterate based on results |
| Job duplicates across sources | Low | Strong deduplication logic using multiple fields |
| Scraper breakage | Medium | Focus on stable ATS platforms, version scrapers, fallback to APIs |

### Product Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Scores don't match reality | High | Manual validation, user feedback loop, iterative improvement |
| Missing relevant jobs | High | Use multiple sources, regularly audit coverage |
| Too many false positives | Medium | Tune filtering thresholds, add more criteria |
| User finds UI confusing | Low | Keep it simple, user testing, iterate on feedback |

---

## Appendix

### Useful Resources

**APIs & Tools**:
- JSearch API (OpenWebNinja): https://www.openwebninja.com/api/jsearch/docs
- Serply job search: https://serply.io/docs
- spaCy: https://spacy.io/
- FastAPI: https://fastapi.tiangolo.com/
- React Query: https://tanstack.com/query/

**Learning Resources**:
- Text similarity with scikit-learn: https://scikit-learn.org/stable/modules/feature_extraction.html
- Web scraping ethics: https://www.scrapehero.com/web-scraping-legal-issues/
- FastAPI tutorial: https://fastapi.tiangolo.com/tutorial/

### Glossary

- **Hard Criteria**: Must-have requirements that filter out jobs completely
- **Soft Criteria**: Preferences that affect scoring but don't eliminate jobs
- **Match Score**: Numerical representation of job-candidate fit (0-100%)
- **ATS**: Applicant Tracking System (software companies use to manage hiring)
- **TF-IDF**: Term Frequency-Inverse Document Frequency (text analysis method)

---

**End of Project Plan**

This document should be treated as a living document. Update as the project evolves and requirements change.
