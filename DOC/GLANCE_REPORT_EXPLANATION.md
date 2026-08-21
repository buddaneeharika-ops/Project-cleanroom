# Country Glance Report — Detailed Explanation & Queries

This document explains the mathematical formulas, database queries, and data granularities used to generate the **Country Glance Report**.

---

## 📊 1. Report Granularities & Core Calculations

The report is divided into two categories of data points:
1. **ECI Data Points (AC-wise)**: Calculations are done at the **Assembly Constituency (AC)** level.
2. **Other Sources (District/LGD-wise)**: Calculations are done at the **District** or **Local Government Directory (LGD)** level.

---

### A. ECI Data Points (AC-wise)

#### 1. Retro Data
* **Description**: Historical candidate and party-wise voting results for each election.
* **Granularity**: Candidate/Party-wise votes per AC.
* **Calculation Formula**:
  $$\text{Retro Data \%} = \frac{\sum \text{Distinct ACs per election in } \mathtt{election\_result}}{\sum \text{Distinct ACs per election in } \mathtt{ac\_election\_mapping}} \times 100$$
  *(Excludes Bypolls (`-BP`) from both numerator and denominator to ensure standard election comparisons).*
* **Example (Andhra Pradesh)**:
  * Expected AC-elections: 1,446
  * Available AC-elections: 1,400
  * **Result**: $96.82\%$

#### 2. Form 20 Data
* **Description**: Polling station-wise candidate vote counts scraped from CEO websites.
* **Granularity**: Booth-wise candidate votes.
* **Calculation Formula**:
  $$\text{Form 20 \%} = \frac{\sum \text{Distinct ACs per election in } \mathtt{form20\_summary\_view}}{\sum \text{Distinct ACs per election in } \mathtt{ac\_election\_mapping}} \times 100$$
  *(Excludes Bypolls (`-BP`)).*
* **Example (Andhra Pradesh)**:
  * Expected AC-elections: 1,446
  * Available AC-elections: 1,299
  * **Result**: $89.83\%$

#### 3. Caste Data
* **Description**: Demographic and caste breakdown percentages by constituency.
* **Granularity**: AC-wise caste composition.
* **Calculation Formula**:
  $$\text{Caste Data \%} = \frac{\text{Distinct ACs in } \mathtt{caste\_details}}{\text{Canonical AC Count of the State } (\mathtt{STATE\_AC\_COUNTS})} \times 100$$
* **Example (Bihar)**:
  * Total ACs: 243
  * Covered ACs: 243
  * **Result**: $100.00\%$

#### 4. Booth Details
* **Description**: Mapped voter registers, polling station locations, and geocodes.
* **Granularity**: Booth-wise voter counts and village profiles.
* **Calculation Formula**:
  $$\text{Booth Details \%} = \frac{\text{Distinct ACs in } \mathtt{booth\_metadata\_full\_view}}{\text{Canonical AC Count of the State } (\mathtt{STATE\_AC\_COUNTS})} \times 100$$
* **Example (Karnataka)**:
  * Total ACs: 224
  * Covered ACs: 224
  * **Result**: $100.00\%$

---

### B. Available Data of Other Sources (District/LGD-wise)

For these sources, availability is computed by comparing the number of districts or LGD codes present in the source table against the master list in the **Local Government Directory (LGD)**.

#### 1. Muslim Census
* **Formula**:
  $$\text{Muslim Census \%} = \frac{\text{Distinct districts in } \mathtt{muslim\_census}}{\text{Total districts in } \mathtt{lgd\_directory}} \times 100$$
* **Example (Andhra Pradesh)**:
  * Mapped Districts: 13
  * LGD Districts: 27
  * **Result**: $48.15\%$

#### 2. Joshua (Joshua Project Population)
* **Formula**:
  $$\text{Joshua \%} = \frac{\text{Distinct districts in } \mathtt{joshua\_population}}{\text{Total districts in } \mathtt{lgd\_directory}} \times 100$$
* **Example (Andhra Pradesh)**:
  * Mapped Districts: 26
  * LGD Districts: 27
  * **Result**: $96.30\%$

#### 3. Ejalshakti (Ministry of Jal Shakti Portal)
* **Formula**:
  $$\text{Ejalshakti \%} = \frac{\text{Distinct LGD codes in } \mathtt{ejalshakti\_portal}}{\text{Total LGD codes in } \mathtt{lgd\_directory}} \times 100$$
* **Example (Andhra Pradesh)**:
  * Mapped LGD Codes: 10,594
  * Master LGD Codes: 13,428
  * **Result**: $78.89\%$

#### 4. SECC (Socio-Economic & Caste Census)
* **Formula**:
  $$\text{SECC \%} = \frac{\text{Distinct LGD codes in } \mathtt{secc\_abstract}}{\text{Total LGD codes in } \mathtt{lgd\_directory}} \times 100$$
* **Example (Andhra Pradesh)**:
  * Mapped LGD Codes: 12,629
  * Master LGD Codes: 13,428
  * **Result**: $94.05\%$

---

## 🗄️ 2. Core SQL Queries & Explanations

Here are the SQL queries executed against the PostgreSQL database to obtain the raw data for the report:

### 1. Expected Elections & AC Counts (`Actual`)
Retrieves the master list of expected elections and counts how many Assembly Constituencies (ACs) should exist for each.
```sql
SELECT
  aem.state_abb AS ST,
  TO_CHAR(aem.el_year, 'FM9999') AS el_year,
  aem.el_type,
  s.state_name,
  COUNT(DISTINCT ac_no) AS No_of_ACS,
  aem.state_abb || '-' || aem.el_type || '-' || aem.el_year AS KEY
FROM ac_election_mapping aem
LEFT JOIN state s ON s.state_abb = aem.state_abb
GROUP BY
  aem.state_abb,
  aem.el_year,
  aem.el_type,
  s.state_name;
```

### 2. AC-PC Mapping
Retrieves geographical relationships between Assembly Constituencies (ACs) and Parliamentary Constituencies (PCs).
```sql
SELECT 
  am.*, 
  s.state_name,
  pr.pc_name,
  am.pc_id AS ac_pc_id,       
  pr.pc_id AS region_pc_id    
FROM ac_mapping am
LEFT JOIN state s 
  ON s.state_abb = am.state_abb
LEFT JOIN pc_region pr 
  ON pr.pc_id = am.pc_id;
```

### 3. Caste Count
Counts how many constituencies per state have active caste data profiles.
```sql
WITH t1 AS (
  SELECT DISTINCT 
    cd.ac_no, 
    cd.state_abb
  FROM caste_details cd
)
SELECT 
  t1.state_abb AS ST, 
  s.state_name, 
  COUNT(t1.ac_no) AS count_caste
FROM t1
LEFT JOIN state s ON s.state_abb = t1.state_abb
GROUP BY t1.state_abb, s.state_name
ORDER BY t1.state_abb;
```

### 4. Caste Details & Voter Percentage
Aggregates the demographic voter counts and weights the caste representation based on constituency voter sizes.
```sql
WITH t1 AS (
    SELECT 
        cd.caste_name,
        cd.caste_category,
        cd.caste_sub_name,
        ad.ac_no,
        cd.state_abb,
        CAST(cd.caste_percentage * ad.total_electoral_count AS INTEGER) AS total_votes
    FROM caste_details cd
    INNER JOIN ac_details ad  
        ON cd.ac_no = ad.ac_no and cd.state_abb = ad.state_abb
),
t2 AS (
    SELECT 
        t1.state_abb,
        t1.caste_name,
        t1.caste_sub_name,
        t1.caste_category,
        SUM(t1.total_votes) AS total_voters,
        ROW_NUMBER() OVER (
            PARTITION BY t1.state_abb 
            ORDER BY SUM(t1.total_votes) DESC
        ) AS rankk
    FROM t1
    GROUP BY 
        t1.state_abb, 
        t1.caste_name, 
        t1.caste_sub_name, 
        t1.caste_category
),
t3 AS (
    SELECT 
        t2.*,
        ROUND(
            total_voters * 100.0 / 
            SUM(total_voters) OVER (PARTITION BY state_abb), 
            2
        ) AS caste_percentage 
    FROM t2
),
ranked_data AS (
    SELECT 
        state_abb,
        caste_name,
        total_voters,
        rankk,
        caste_category,
        caste_sub_name,
        caste_percentage
    FROM t3
),
caste_cte AS (
  SELECT 
    state_abb,
    CASE 
      WHEN caste_percentage > 1 THEN caste_name
      ELSE 'Others'
    END AS caste_name,
    CASE 
      WHEN caste_percentage > 1 THEN caste_sub_name
      else 'Others'
    END AS caste_sub_name,
    caste_category,
    SUM(total_voters) AS total_voters,
    SUM(caste_percentage) AS caste_percentage
  FROM ranked_data
  GROUP BY 
    state_abb,
    caste_category,
    CASE 
      WHEN caste_percentage > 1 THEN caste_name
      ELSE 'Others'
    END,
    CASE 
      WHEN caste_percentage > 1 THEN caste_sub_name
      ELSE 'Others'
    END
)
SELECT 
  state_abb,
  caste_name,
  caste_sub_name,
  caste_category,
  caste_percentage
FROM caste_cte;
```

### 5. Form 20 Availability
Gathers statistics of Form 20 entries pushed to the database per election.
*(Note: To query this table, utilize the view `public.form20_summary_view` to avoid permission blocks on the raw table)*
```sql
 WITH t1 AS (
  SELECT 
    f.*, 
    f.el_id AS f_el_id
  FROM form20_summary_view f
),
t2 AS (
  SELECT 
    t1.state_abb,
    e.el_type,
    TO_CHAR(e.el_year, 'FM9999') AS el_year,
    s.state_name,
    SUM(t1.votes) AS total_votes,
    COUNT(DISTINCT t1.ac_no) AS number_of_acs
  FROM t1
  LEFT JOIN election e ON e.el_id = t1.el_id
  LEFT JOIN state s ON s.state_abb = t1.state_abb
  GROUP BY 
    t1.state_abb, e.el_type, e.el_year, s.state_name
)
SELECT 
  t2.*,
  t2.state_abb || '-' || t2.el_type || '-' || t2.el_year AS key
FROM t2;
```

### 6. Local Government Directory (LGD) Master Count
Retrieves counts of districts, blocks, sub-districts, and villages registered in the LGD directory.
```sql
SELECT 
    ld.state_abb,
    COUNT(DISTINCT ld.district_code) AS district_count,
    COUNT(DISTINCT ld.sub_district_code) AS sub_district_count,
    COUNT(DISTINCT ld.village_code) AS village_count,
    COUNT(DISTINCT ld.lgd_code) as LGD_Count
FROM lgd_directory ld;
```

### 7. Historical Results (`Retro%`)
Counts how many constituencies have historical election results stored in the database.
```sql
WITH t1 AS (
  SELECT 
    er.state_abb,
    e.el_type,
    e.el_year,
    er.ac_no
  FROM election_result er
  LEFT JOIN election e ON e.el_id = er.el_id
),
t2 AS (
  SELECT 
    t1.state_abb,
    t1.el_type,
    TO_CHAR(t1.el_year, 'FM9999') AS el_year,
    COUNT(DISTINCT t1.ac_no) AS total_ac
  FROM t1
  GROUP BY 
    t1.state_abb, t1.el_type, t1.el_year
)
SELECT 
  t2.*, 
  t2.state_abb || '-' || t2.el_type || '-' || t2.el_year AS key
FROM t2;
```

### 8. District Count Table
Counts master districts mapped per state.
```sql
SELECT
  state_abb,
  COUNT(district_name) AS District_Count
FROM district d
GROUP BY state_abb;
```

### 9. Ejalshakti
Checks the intersection of active Ejalshakti villages against the LGD directory database.
```sql
SELECT
  ld.state_abb,
  COUNT(DISTINCT ep.village_name) AS village_count,
  COUNT(DISTINCT ep.lgd_code) AS Ejal_lgd_code_count
FROM ejalshakti_portal ep
LEFT JOIN lgd_directory ld 
    ON ld.lgd_code = ep.lgd_code
GROUP BY ld.state_abb
ORDER BY ld.state_abb;
```

### 10. Joshua Population Mappings
Calculates district-level population statistics availability from the Joshua project database.
```sql
SELECT
  jp.state_abb,
  COUNT(DISTINCT jp.district_name) AS JOSHUA_district_count
FROM joshua_population jp
GROUP BY jp.state_abb;
```

### 11. School Locator Mappings (KYS)
Retrieves the number of districts covered with school locator geocodes.
```sql
SELECT
  sl.state_abb,
  COUNT(DISTINCT sl.district_name) AS KYS_distinct_count
FROM school_locator sl
GROUP BY  sl.state_abb
ORDER BY sl.state_abb;
```

### 12. Muslim Census Mappings
Retrieves demographic records representing census percentages per district.
```sql
SELECT
  mc.state_abb,
  COUNT(DISTINCT mc.district_name) AS MUSLIM_district_count
FROM muslim_census mc
GROUP BY mc.state_abb;
```

### 13. SECC Mappings
Retrieves household socio-economic status codes mapped to LGD village structures.
```sql
SELECT
  sa.state_abb,
  COUNT(DISTINCT sa.lgd_code) AS SECC_lgd_code_count
FROM secc_abstract sa
GROUP BY sa.state_abb
ORDER BY sa.state_abb;
```
