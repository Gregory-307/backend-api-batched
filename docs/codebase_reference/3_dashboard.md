# Codebase Reference: Dashboard & UI Components

This document provides a summary of the Python files that create the Streamlit web dashboard, including the main pages and key reusable visualization components from the `hb_components` library.

---

## 1. `dashboard/pages/1_Documentation.py`

*   **Purpose**: Serves as a dynamic, explorable knowledge base for the project.  This is the **first visible page** when the dashboard launches.
*   **Key Features**:
    *   Renders a landing page with large, clickable buttons for accessing documentation.
    *   Buttons are grouped into logical sections like "Getting Started", "How-To", "Concepts", and "Codebase Reference".
    *   Includes a sidebar search box to filter the documents by title in real-time.
    *   When a button is clicked, it reads the corresponding Markdown file from the `docs/` directory and displays its content on the page.
*   **Interaction**: This page is data-driven; it automatically discovers and categorizes `.md` files, making it easy to maintain.

---

## 2. `dashboard/pages/2_Experiments_Overview.py`

*   **Purpose**: The main dashboard for analyzing and comparing the results of a batch test run.
*   **Key Features**:
    *   Allows the user to select a `*results.csv` file from a specified directory.
    *   Displays high-level, batch-wide performance KPIs (e.g., "Avg Net PNL", "Avg Volume").
    *   Features an interactive Ag-Grid "Leaderboard" table to sort and filter individual runs.
    *   Presents a variety of Plotly charts (box, scatter, bar, histogram) to visualize the distribution of metrics like PnL, profit factor, and accuracy.
    *   Wrapped in `st.container()` to ensure the layout never overflows the viewport.
*   **Usage**: This is the primary interface for getting a high-level understanding of a parameter sweep's performance.

---

## 3. `dashboard/pages/3_Top_5.py`

*   **Purpose**: Provides a more detailed, side-by-side comparison of the top-performing runs from a results CSV.
*   **Key Features**:
    *   Lets the user select the KPI by which to rank the runs (e.g., `net_pnl_quote`, `sharpe_ratio`).
    *   Displays the top 5 runs based on the selected metric.
    *   For each of the top 5 runs, it shows a dedicated panel containing:
        *   A full backtesting figure (price chart + trades).
        *   A block of detailed performance metrics.
        *   An "expander" to view the full configuration parameters for that specific run.
*   **Usage**: Ideal for quickly identifying the most successful configurations and visually confirming their trading behavior.

---

## 4. `dashboard/pages/4_Sweep_Analysis.py`

*   **Purpose**: Allows in-depth analysis of an entire parameter sweep file, including KPI distributions and correlation plots.
*   **Key Features**:
    *   Interactive filters for any column in the results CSV.
    *   Pair-plots, heatmaps, and scatter matrices to surface parameter interactions.
    *   Ability to drill down to a single run by clicking a point, which routes the user to the Experiment Analysis page.
*   **Usage**: Best suited for research scenarios where you want to understand how multiple parameters influence performance across hundreds of runs.

---

## 5. `dashboard/pages/5_Experiment_Analysis.py`

*   **Purpose**: The most granular view, offering a deep dive into a single, specific back-test run.
*   **Key Features**:
    *   Uses a sidebar dropdown to select any run by its unique `label` from the `results/detail_packets/` directory.
    *   Displays all available metrics and charts for that single run, including KPIs, the main backtesting figure, and a detailed trade-by-trade log table.
    *   Shows the full run configuration parameters in an expandable JSON viewer.
*   **Usage**: The go-to page for forensic analysis of a single strategy's performance.

---

## 6. `dashboard/theme_overrides.py`

*   **Purpose**: Injects custom CSS into the Streamlit application to achieve a consistent, modern, Tailwind-inspired dark theme.
*   **Key Features**:
    *   Loads the "Inter" Google Font.
    *   Defines CSS classes for custom components like `.kpi-card`, `.badge-buy`/`.badge-sell`, and `.big-btn` for the docs page.
    *   Sets global styles for colors, fonts, and backgrounds.
*   **Usage**: Imported once in `Home.py` to apply its styles across the entire application.

---

## 7. `dashboard/hb_components/backtesting.py`

*   **Purpose**: A reusable component that generates the main 2-row backtesting figure.
*   **Key Components**:
    *   `create_backtesting_figure()`: A function that orchestrates the creation of the chart.
    *   It uses `plotly.subplots` to create a figure with a top row for the price chart and a bottom row for the cumulative PnL chart.
    *   It calls other components to get the individual traces (`get_bt_candlestick_trace`, `add_executors_trace`, `get_pnl_trace`) and assembles them into a single, coherent figure.
*   **Usage**: Imported by `2_Experiments_Overview.py`, `3_Top_5.py`, and `5_Experiment_Analysis.py` to avoid code duplication and ensure a consistent look for the main visualization.

---

## 8. `dashboard/hb_components/backtesting_metrics.py`

*   **Purpose**: A reusable component for rendering standardized blocks of Key Performance Indicators (KPIs).
*   **Key Components**:
    *   `render_backtesting_metrics()`: Takes the `results` dictionary from a backtest and displays the main financial metrics (Net PNL, Max Drawdown, Sharpe Ratio, etc.) using `st.metric`.
    *   `render_accuracy_metrics()` and `render_close_types()`: Helper functions to display specialized KPI groups.
*   **Usage**: Used across multiple dashboard pages to present metrics in a consistent format.

---

## 9. `dashboard/hb_components/pnl.py`

*   **Purpose**: A focused component responsible for generating the cumulative Profit and Loss (PnL) trace.
*   **Key Components**:
    *   `get_pnl_trace()`: Takes a list of executor objects, calculates the cumulative sum of `net_pnl_quote`, and returns a Plotly `Scatter` trace (a dashed gold line).
*   **Usage**: Called by `create_backtesting_figure()` to create the PnL subplot.

---

## 10. `dashboard/hb_components/executors.py`

*   **Purpose**: A reusable component that draws the trade overlays on a price chart.
*   **Key Components**:
    *   `add_executors_trace()`: Iterates through a list of executor objects. For each one, it draws a line from the trade's entry time/price to its exit time/price.
    *   The line is colored green for profitable trades, red for losing trades, and grey/dashed for trades with zero PnL.
*   **Usage**: Called by `create_backtesting_figure()` to visualize where trades occurred on the candlestick chart.

## 11. `dashboard/hb_components/candles.py`

*   **Purpose**: A reusable UI component that provides functions for generating candlestick and price line traces for Plotly charts.
*   **Key Components**:
    *   `get_bt_candlestick_trace()`: Creates a lightweight line trace of the close price, optimized for backtesting visualizations.
    *   `get_candlestick_trace()`: Generates a full OHLCV candlestick trace for detailed price action analysis.
*   **Usage**: Imported by various dashboard pages to render price charts consistently.

## 12. `dashboard/ui_helpers.py`

*   **Purpose**: Contains helper functions to create styled, reusable UI elements for the Streamlit dashboard, following a consistent design language.
*   **Key Components**:
    *   `kpi_card()`: Renders a "Key Performance Indicator" card with a label and a value, often used to display primary metrics.
    *   `styled_container()`: A context manager that wraps a Streamlit container in a `div` with a specific CSS class, allowing for custom styling.
*   **Usage**: Used throughout the dashboard pages to build a clean and consistent user interface.

## 13. `dashboard/hb_components/signals.py`
*   **Purpose**: A reusable UI component that generates Plotly traces to visualize buy and sell signals on a chart.
*   **Key Features**:
    *   Creates two `Scatter` traces: one for buy signals and one for sells.
    *   Buy signals are represented by upward-pointing green triangles, and sells by downward-pointing red triangles.
    *   The size of the marker is scaled based on the trade's quote amount, providing a visual cue for trade size.
*   **Usage**: Called by the backtesting figure component to overlay trade signals on the price chart.

## 14. `dashboard/hb_components/theme.py`
*   **Purpose**: Centralizes the visual styling for the dashboard to ensure a consistent look and feel.
*   **Key Components**:
    *   `get_color_scheme()`: Returns a dictionary of colors used for different chart elements (e.g., price, buy, sell, MACD line).
    *   `get_default_layout()`: Returns a default Plotly `layout` object configured for a dark theme, with standardized fonts, margins, and legend positioning.
*   **Usage**: These functions are used by all chart-generating components to maintain a consistent visual identity.

## 15. `dashboard/packet_index.py`
*   **Purpose**: A performance optimization utility for the dashboard that manages an index of backtest result files (detail packets).
*   **Key Features**:
    *   Maintains a CSV file (`results/detail_packets/_index.csv`) that stores metadata about each result JSON file (path, size, modified time).
    *   This allows the dashboard to load and display a list of all available backtest runs very quickly, without needing to parse every large JSON file on startup.
    *   Provides a `load_packet()` function to load a specific JSON file on demand when a user selects it for viewing.
*   **Usage**: This is a critical component for making the dashboard feel responsive, especially when there are hundreds or thousands of result files. 