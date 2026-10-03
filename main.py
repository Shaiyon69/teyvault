# Entry point for `flet build` (Android / iOS) and `flet pack` (Windows installer).
import sys

if "--weblogin" in sys.argv:  # the installed exe re-launched by weblogin.sign_in()
    from teyvat.weblogin import _main
    _main()
else:
    from teyvat.gui import run
    run()
