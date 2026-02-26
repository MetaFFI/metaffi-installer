FROM mcr.microsoft.com/windows/servercore:ltsc2022

# TODO: implement after Linux Dockerfile works
SHELL ["powershell", "-Command"]
COPY metaffi-installer.exe C:\\temp\\metaffi-installer.exe
RUN C:\\temp\\metaffi-installer.exe -s ; \
    Remove-Item C:\\temp\\metaffi-installer.exe

RUN metaffi --help
