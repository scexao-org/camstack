# Makefile for creating our standalone Cython program
#version=$(python --version | awk '{ print $2 }')
#split=( ${version//./ } )

PYVERSION=3.8
PYPREFIX=${HOME}/anaconda3/
INCLUDES=-I${HOME}/anaconda3/include/python${PYVERSION}
LIBS=-L${HOME}/anaconda3/lib/

NAME=make_cset_and_rt

${NAME}: ${NAME}.o
	gcc -o $@ $^ ${LIBS} -lpython${PYVERSION}

${NAME}.o: ${NAME}.c
	gcc -c $^ $(INCLUDES)

${NAME}.c: ${NAME}.py
	@python -m cython --embed ${NAME}.py

all: ${NAME}
	sudo chown root:root ${NAME}
	sudo chmod u+s ${NAME}

clean:
	@echo Cleaning Demos/embed
	@rm -f *~ *.o *.so core core.* *.c ${NAME}
