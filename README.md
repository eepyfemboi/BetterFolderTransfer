# BetterFolderTransfer
a kinda simple python script i made to transfer a large folder to an external driver on windows, since when i tried to move it using windows explorer it never worked

basically it moves a folder from one drive to another, and as it finishes moving a file, it checks the hash of the file then deletes the file from the origin, and before moving each file it checks if it already exists in the destination

it also accounts for interrupts like if a drive is disconnected mid transfer

kinda broken rn but still working on it
