$ErrorActionPreference = "Stop"

Write-Host "[1/4] Pobieram liste elektrowni..."
python .\L02\download_plant_locations.py --output .\L02\plant.json

Write-Host "[2/4] Pobieram lokalizacje osob..."
python .\L02\fetch_people_locations.py --input .\L02\people_out.csv --output .\L02\locations.json

Write-Host "[3/4] Pobieram access levels..."
python .\L02\fetch_access_levels.py --input .\L02\people_out.csv --output .\L02\access_levels.json

Write-Host "[4/4] Rozwiazuje findhim i wysylam verify..."
python .\L02\solve_findhim.py --input .\L02\people_out.csv --plants .\L02\plant.json --report .\L02\findhim_report.json --candidates .\L02\findhim_candidates.json --max-distance-km 2.0 --verify

Write-Host "Gotowe."