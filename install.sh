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

# Check for install dependency availability
if ! [ -x "$(command -v curl)" ]; then
       echo "❌ curl is required to execute the installation. Please install it and run the installer again!"
       exit
fi
if ! [ -x "$(command -v unzip)" ]; then
       echo "❌ Unzip is required to execute the installation. Please install it and run the installer again!"
       exit
fi
if ! [ -x "$(command -v sudo)" ]; then
       echo "❌ sudo is required to execute the installation. Please install it and run the installer again!"
       exit
fi
if ! [ -x "$(command -v install)" ]; then
       echo "❌ install is required to execute the installation. Please install it and run the installer again!"
       exit
fi

download_url=$(curl -L -s https://api.github.com/repos/gefyrahq/gefyra/releases/latest | grep '"browser_download_url": ".*'$OS'.*"' | grep -Eo "(http|https)://[a-zA-Z0-9./?=_%:-]*")
file_name=$(echo $download_url | grep -oE '[^/]+$')
curl -L $download_url -o /tmp/$file_name
unzip -o /tmp/$file_name -d /tmp/gefyra
sudo install -m 0755 /tmp/gefyra/gefyra /usr/local/bin/gefyra

# cleanup 
rm -rf /tmp/$file_name
rm -rf /tmp/deck

# additional information
echo ""
echo "🎉 Gefyra has been successfully installed"
echo ""
echo "🚀 Here's our getting started guide: https://gefyra.dev/getting-started/ "
echo "💡 Some exciting use cases: https://gefyra.dev/usecases/ "
echo ""
echo "❓ Any problems? Feel free to provide us with feedback: https://github.com/gefyrahq/gefyra/issues/ "
