"""
Create PowerPoint-ready chart from Excel data
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from openpyxl import load_workbook
import os

# Set style for professional charts
sns.set_style("whitegrid")
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['font.size'] = 12
plt.rcParams['axes.labelsize'] = 14
plt.rcParams['axes.titlesize'] = 16
plt.rcParams['xtick.labelsize'] = 11
plt.rcParams['ytick.labelsize'] = 11
plt.rcParams['legend.fontsize'] = 11

def create_chart_from_excel(excel_path):
    """
    Read Excel file and create PowerPoint-ready chart

    Args:
        excel_path: Path to Excel file
    """
    print(f"Reading Excel file: {excel_path}")

    # Try to read the Excel file
    try:
        # First, let's see what sheets are available
        xls = pd.ExcelFile(excel_path)
        print(f"\nAvailable sheets: {xls.sheet_names}")

        # Read the first sheet
        df = pd.read_excel(excel_path, sheet_name=0)
        print(f"\nData preview:")
        print(df.head(20))
        print(f"\nShape: {df.shape}")
        print(f"\nColumns: {df.columns.tolist()}")

        # Also check if there are any charts in the Excel file
        wb = load_workbook(excel_path)
        ws = wb.active

        if hasattr(ws, '_charts') and ws._charts:
            print(f"\nFound {len(ws._charts)} chart(s) in the Excel file")

        # Create output directory
        os.makedirs('.tmp/charts', exist_ok=True)

        # Determine chart type based on data structure
        # This is a flexible approach that handles different data formats

        if len(df.columns) == 2:
            # Simple two-column data - likely category vs value
            fig, ax = plt.subplots(figsize=(12, 7))

            # Determine if we should use bar chart or line chart
            # If first column looks like dates or sequential, use line chart
            first_col = df.columns[0]
            second_col = df.columns[1]

            # Try to detect if it's time series data
            try:
                df[first_col] = pd.to_datetime(df[first_col])
                is_timeseries = True
            except:
                is_timeseries = False

            if is_timeseries:
                # Line chart for time series
                ax.plot(df[first_col], df[second_col],
                       marker='o', linewidth=2.5, markersize=8,
                       color='#2E86AB', markerfacecolor='#A23B72')
                ax.set_xlabel(first_col, fontweight='bold')
                ax.set_ylabel(second_col, fontweight='bold')
                plt.xticks(rotation=45, ha='right')
                ax.grid(True, alpha=0.3, linestyle='--')
            else:
                # Bar chart for categorical data
                colors = plt.cm.Set3(range(len(df)))
                bars = ax.bar(df[first_col], df[second_col],
                             color=colors, edgecolor='black', linewidth=1.2)
                ax.set_xlabel(first_col, fontweight='bold')
                ax.set_ylabel(second_col, fontweight='bold')
                plt.xticks(rotation=45, ha='right')
                ax.grid(True, alpha=0.3, axis='y', linestyle='--')

                # Add value labels on bars
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:,.0f}',
                           ha='center', va='bottom', fontweight='bold')

            ax.set_title('Savings Overview', fontsize=18, fontweight='bold', pad=20)
            plt.tight_layout()

            # Save as high-res PNG for PowerPoint
            output_path = '.tmp/charts/savings_chart_ppt.png'
            plt.savefig(output_path, dpi=300, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            print(f"\n✓ Chart saved to: {output_path}")
            plt.close()

            return output_path

        elif len(df.columns) > 2:
            # Multiple series - create grouped bar or line chart
            fig, ax = plt.subplots(figsize=(14, 8))

            # Use first column as index
            df_plot = df.set_index(df.columns[0])

            # Create line chart with multiple series
            df_plot.plot(ax=ax, marker='o', linewidth=2.5, markersize=8)
            ax.set_xlabel(df.columns[0], fontweight='bold')
            ax.set_ylabel('Value', fontweight='bold')
            ax.set_title('Savings Overview', fontsize=18, fontweight='bold', pad=20)
            ax.legend(title='', loc='best', frameon=True, shadow=True)
            ax.grid(True, alpha=0.3, linestyle='--')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            output_path = '.tmp/charts/savings_chart_ppt.png'
            plt.savefig(output_path, dpi=300, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            print(f"\n✓ Chart saved to: {output_path}")
            plt.close()

            return output_path

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    excel_path = '.tmp/email_attachments/Savings overview01.xlsx'
    if os.path.exists(excel_path):
        create_chart_from_excel(excel_path)
    else:
        print(f"Excel file not found: {excel_path}")
