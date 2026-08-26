run: solver
	mkdir -p outputs
	./solver data/set_01.txt > outputs/answers.txt

solver: solver.rs
	rustc -O -o solver solver.rs

clean:
	rm -f solver
	rm -rf outputs

.PHONY: run clean
