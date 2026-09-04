#!/usr/bin/env bash
# Autostock daily update script
# Switch to project root
dir="C:/My_Project/Hermes/[工作區]/AutoStock"
cd "$dir"
# Update dashboards (fetch data & rewrite HTML)
python update_dashboards.py
# Push to GitHub via existing skill
hermes skill run push_stock_dashboard
