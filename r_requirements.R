# R 4.5.2. Installs the four packages the R scripts need, at the versions
# used for the paper run (later versions likely fine; digit-exact replication
# verified with these): data.table 1.17.8, fixest 0.13.2,
# fwildclusterboot 0.14.3, ivreg 0.6.8.
pkgs <- c("data.table", "fixest", "fwildclusterboot", "ivreg")
miss <- pkgs[!pkgs %in% rownames(installed.packages())]
if (length(miss)) install.packages(miss, repos = "https://cloud.r-project.org")
for (p in pkgs) cat(p, as.character(packageVersion(p)), "
")
