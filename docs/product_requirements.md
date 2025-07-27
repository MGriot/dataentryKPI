# Product Requirements Document: Data Entry KPI Application

## 1. Introduction

*   **Purpose:** This document defines the requirements for the Data Entry KPI application, a tool designed to facilitate the management, entry, calculation, and analysis of Key Performance Indicators (KPIs) across various facilities and time periods.
*   **Scope:** The application covers functionalities for KPI definition, hierarchical organization, target setting (annual and periodic), automated repartitioning, formula-based calculations, master-sub KPI relationships, and data export. It provides two distinct graphical user interfaces: a desktop application built with Tkinter and a web application built with Streamlit.
*   **Target Audience:**
    *   **Business Users:** Individuals responsible for entering KPI target data, analyzing performance, and generating reports.
    *   **Administrators:** Users who define and manage KPI structures, facility information, and system configurations.
    *   **Developers:** Engineers who need to understand the system's architecture, extend its functionality, or integrate with other systems.

## 2. Goals

*   **Efficient Data Entry:** Enable users to input KPI target data accurately and with minimal effort.
*   **Flexible KPI Definition:** Provide tools for defining, categorizing, and organizing KPIs in a hierarchical manner.
*   **Automated Target Repartitioning:** Automatically distribute annual KPI targets into finer periodic granularities (daily, weekly, monthly, quarterly) based on configurable profiles.
*   **Advanced Target Calculation:** Support formula-based target calculations and hierarchical distribution through master-sub KPI relationships.
*   **Intuitive User Interfaces:** Offer user-friendly and responsive graphical interfaces (both desktop and web) for seamless interaction with the application.
*   **Comprehensive Data Analysis:** Facilitate the visualization and analysis of KPI targets across different dimensions.
*   **Robust Data Export:** Allow users to export all relevant KPI data for external reporting, analysis, and integration.
*   **Granular Visibility Control:** Enable administrators to control the visibility of specific KPIs for individual facilities.
*   **Visual Customization:** Provide options to customize visual elements, such as assigning unique colors to facilities for better data differentiation.
*   **Data Integrity:** Ensure the consistency and integrity of all data stored within the application's databases.

## 3. User Stories / Features

### 3.1. KPI Management

*   **As an Administrator, I want to define KPI Groups** so that I can categorize and organize KPIs logically within the system.
*   **As an Administrator, I want to define KPI Subgroups** within existing groups, with the option to link them to indicator templates, so that I can further organize KPIs and inherit default properties for consistency.
*   **As an Administrator, I want to define KPI Indicators** within subgroups so that I can specify the fundamental measurable metrics.
*   **As an Administrator, I want to define KPI Specifications** (including description, calculation type, unit of measure, and global visibility) for each indicator so that I can precisely define how a KPI behaves and is measured.
*   **As an Administrator, I want to manage KPI Indicator Templates** (create, edit, delete) so that I can create reusable definitions for common indicators and propagate changes to linked subgroups and KPIs.
*   **As an Administrator, I want to link Master and Sub-KPIs with definable distribution weights** so that I can establish hierarchical relationships and automatically distribute targets from a master KPI to its sub-KPIs.
*   **As an Administrator, I want to control KPI visibility for each individual Stabilimento** so that I can selectively show or hide specific KPIs in data entry and analysis views based on the facility.

### 3.2. Stabilimento Management

*   **As an Administrator, I want to add, edit, and delete Stabilimenti (Facilities)** so that I can manage the physical locations or entities for which KPIs are tracked.
*   **As an Administrator, I want to assign a unique color to each Stabilimento** so that I can visually distinguish data related to different facilities in charts, tables, and other visual representations.

### 3.3. Target Entry

*   **As a Business User, I want to select a specific Year and Stabilimento** so that I can focus on entering and managing KPI targets relevant to that context.
*   **As a Business User, I want to enter annual target values for KPIs** so that these values can serve as the basis for periodic distribution.
*   **As a Business User, I want to define formula-based targets** so that KPI values can be automatically calculated based on other KPIs, historical data, or custom logic.
*   **As a Business User, I want to configure repartition logic and distribution profiles** (e.g., Even, Progressive, Sinusoidal, Custom Monthly/Quarterly/Weekly) so that annual targets are accurately and automatically distributed to daily, weekly, monthly, or quarterly periods.
*   **As a Business User, I want to manually override derived sub-KPI targets** so that I can make specific adjustments to individual values even if they are part of a master-sub relationship.
*   **As a Business User, I want to save all entered and calculated targets** so that my data is persistently stored and available for future use and analysis.

### 3.4. Data Analysis & Reporting

*   **As a Business User, I want to view periodic KPI targets** (daily, weekly, monthly, quarterly) in both tabular and graphical formats so that I can easily analyze trends, compare performance, and identify deviations.
*   **As a Business User, I want to export all KPI data to CSV or Excel formats** so that I can use it for external reporting, further analysis in other tools, or data archival.

## 4. Technical Requirements (High-Level)

*   **Database:** SQLite will be used as the embedded, file-based database for local data storage, ensuring ease of deployment and portability.
*   **Programming Language:** Python will be the primary programming language for all application logic and interfaces.
*   **GUI Frameworks:**
    *   **Tkinter:** For the desktop application, providing a native look and feel on various operating systems.
    *   **Streamlit:** For the web application, enabling interactive data exploration and accessibility via a web browser.
*   **Modularity:** The codebase will be structured into distinct modules (e.g., GUI, business logic, data access, utility functions) to promote maintainability, testability, and reusability.
*   **Extensibility:** The architecture should allow for the relatively easy addition of new KPI types, distribution profiles, reporting features, or integration points in the future.
*   **Error Handling:** The application must implement robust error handling mechanisms to gracefully manage database errors, invalid user inputs, formula calculation failures, and other unexpected conditions, providing clear feedback to the user.

## 5. Non-Functional Requirements

*   **Performance:**
    *   The user interfaces should be responsive, with minimal lag during data loading, filtering, and saving operations.
    *   Target repartitioning calculations should complete within acceptable timeframes for typical data volumes (e.g., hundreds of KPIs, tens of facilities, several years of data).
*   **Usability:**
    *   Both Tkinter and Streamlit interfaces must be intuitive and easy to navigate for all target users.
    *   Clear and concise labels, instructions, and feedback messages should guide the user through workflows.
*   **Maintainability:**
    *   The codebase should adhere to Python best practices, including clear naming conventions, consistent formatting, and appropriate commenting.
    *   Dependencies should be well-managed and documented.
*   **Scalability:** While primarily designed as a single-user desktop/local web application, the underlying database design and modular architecture should allow for potential future scaling (e.g., migration to a more robust database system for multi-user environments).
*   **Data Integrity:** The application must enforce data integrity and consistency through appropriate database schema design (e.g., foreign keys, unique constraints) and application-level validation logic.

## 6. Future Considerations

*   **External Data Integration:** Implement functionality to import actual KPI data from external sources (e.g., CSV, Excel, APIs) for comparison against targets.
*   **User Management:** Introduce user authentication and authorization mechanisms for multi-user environments, controlling access to different functionalities and data.
*   **Advanced Reporting:** Develop more sophisticated reporting and dashboarding features, including custom report generation and interactive dashboards.
*   **Expanded Profiles:** Add support for a wider range of distribution profiles and more complex formula functions.
*   **Version Control for Data:** Implement a mechanism for tracking changes to KPI definitions and target data over time.
*   **Notifications:** Add a notification system for data anomalies or critical events.
