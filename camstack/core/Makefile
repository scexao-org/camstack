# Makefile for creating our standalone Cython program
PYVERSION=3.8
PYPREFIX=/usr
INCLUDES=-I$(PYPREFIX)/include/python$(PYVERSION)

NAME=make_cset_and_rt

${NAME}: ${NAME}.o
	gcc -o $@ $^ -lpython$(PYVERSION)

${NAME}.o: ${NAME}.c
	gcc -c $^ $(INCLUDES)

${NAME}.c: ${NAME}.py
	@python -m cython --embed ${NAME}.py

all: ${NAME}
	chown root:root ${NAME}
	chmod u+s ${NAME}

clean:
	@echo Cleaning Demos/embed
	@rm -f *~ *.o *.so core core.* *.c ${NAME}
