-- main.lua
local filename = arg[1] or "dataset.csv"

-- Load CSV into DuckDB
os.execute('duckdb iris.duckdb "CREATE TABLE IF NOT EXISTS iris AS SELECT * FROM read_csv_auto(\'' .. filename .. '\');"')
os.execute('duckdb iris.duckdb "COPY (SELECT sepal_length, sepal_width, petal_length, petal_width FROM iris) TO \'temp.csv\' (HEADER FALSE);"')

local data = {}
for line in io.lines("temp.csv") do
    local sl, sw, pl, pw = line:match("([^,]+),([^,]+),([^,]+),([^,]+)")
    if sl then
        table.insert(data, {tonumber(sl), tonumber(sw), tonumber(pl), tonumber(pw)})
    end
end
os.execute('rm temp.csv')

-- Mean of each column
local means = {0, 0, 0, 0}
local n = #data
for i=1,n do
    for j=1,4 do
        means[j] = means[j] + data[i][j]
    end
end
for j=1,4 do
    means[j] = means[j] / n
end

-- Covariance matrix
local cov = {}
for i=1,4 do cov[i] = {0, 0, 0, 0} end

for i=1,n do
    for j=1,4 do
        for k=1,4 do
            -- Compute covariance
            cov[j][k] = cov[j][k] + ((data[i][j] - means[j]) * (data[i][k] - means[k])) / n
        end
    end
end

-- Power iteration for first PCA eigenvalue
local function power_iteration(matrix, iterations)
    local v = {1, 1, 1, 1}
    for _ = 1, iterations do
        local next_v = {0, 0, 0, 0}
        for j = 1, 4 do
            for k = 1, 4 do
                next_v[j] = next_v[j] + matrix[j][k] * v[k]
            end
        end
        local norm = 0
        for j = 1, 4 do norm = norm + next_v[j]*next_v[j] end
        norm = math.sqrt(norm)
        for j = 1, 4 do v[j] = next_v[j] / norm end
    end
    local num = 0
    local den = 0
    for j = 1, 4 do
        local mv = 0
        for k = 1, 4 do mv = mv + matrix[j][k] * v[k] end
        num = num + v[j] * mv
        den = den + v[j] * v[j]
    end
    return num / den
end

local eig1 = power_iteration(cov, 50)

-- Write results back to DuckDB
local f = io.open("insert_results.sql", "w")
f:write("CREATE TABLE IF NOT EXISTS covariance (i INT, j INT, val FLOAT);\n")
f:write("DELETE FROM covariance;\n")
for j=1,4 do
    for k=1,4 do
        f:write(string.format("INSERT INTO covariance VALUES (%d, %d, %0.15f);\n", j, k, cov[j][k]))
    end
end
f:write("CREATE TABLE IF NOT EXISTS pca (component INT, eigenvalue FLOAT);\n")
f:write("DELETE FROM pca;\n")
f:write(string.format("INSERT INTO pca VALUES (1, %0.15f);\n", eig1))
f:close()

os.execute('duckdb iris.duckdb < insert_results.sql')
