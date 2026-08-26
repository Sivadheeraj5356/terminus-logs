function main()
    lines = readlines(ARGS[1])
    open(ARGS[2], "w") do io
        for line in lines[2:end]
            s = strip(line)
            isempty(s) && continue
            t = split(s)
            length(t) < 4 && continue
            L = parse(Int, t[3])
            println(io, "$(t[1]) $(lpad("0", 2L, '0'))")
        end
    end
end

main()
