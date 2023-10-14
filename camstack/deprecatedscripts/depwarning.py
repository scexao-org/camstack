def print_dep_warning(orig_script: str, new_script: str):
    print('-' * 60, '-' * 60, f'{"DEPRECATION WARNING": ^60s}',
          f'{orig_script: ^60s}',
          f'{"will be deprecated sometime soon. Use instead:": ^60s}',
          f'{new_script: ^60s}',
          f'{"Feel free to address all complaints to /dev/null!": ^60s}',
          '-' * 60, '-' * 60, sep='\n')
