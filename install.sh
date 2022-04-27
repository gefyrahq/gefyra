OS="`uname`"
case $OS in
	'Linux')
		OS=linux
		echo "Detected Linux! (Congratulations!)"
		;;
	'Darwin')
		OS=darwin
		echo "Detected MacOS"
		;;
	*)
		echo "No supported platform detected"
		exit 1
		;;
esac

ARCH="`uname -m`"

if [ "$OS" = "darwin" ] && [ "$ARCH" != "x86_64" ]
then
	echo "Currently we only support Darwin amd64/x86_64. Stay tuned!"
	exit 1
fi

download_url=$(curl -L -s https://api.github.com/repos/gefyrahq/gefyra/releases/latest | grep '"browser_download_url": ".*'$OS'.*"' | grep -Eo "(http|https)://[a-zA-Z0-9./?=_%:-]*")
file_name=$(echo $download_url | grep -oE '[^/]+$')
curl -L $download_url -o /tmp/$file_name
unzip -o /tmp/$file_name -d /tmp/gefyra
sudo install -o root -g root -m 0755 /tmp/gefyra/gefyra /usr/local/bin/gefyra
