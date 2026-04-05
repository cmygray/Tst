"""python -m tst 로 실행할 수 있게 하는 엔트리포인트."""

import multiprocessing

multiprocessing.freeze_support()

from tst.app import main

main()
